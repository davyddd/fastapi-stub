import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any, Protocol, Self

from share.kafka.consumer import BaseKafkaConsumerRepository, Deserializable


class Lockable(Protocol):
    # How long one `extend` is worth. A streaming consumer has to beat faster than this, so the
    # contract has to say it out loud rather than leave it to whoever wires the lock up.
    timeout: float

    async def acquire(self) -> None: ...

    async def release(self) -> None: ...

    async def extend(self) -> None: ...


class ConsumerStartError(Exception): ...


# How much of the lock's timeout a streaming consumer is allowed to spend between two beats.
# The rest is headroom for the one thing the check cannot see — how long the caller takes over
# a batch, which is bounded by nothing here.
MAX_BEAT_SHARE_OF_LOCK_TIMEOUT = 0.5


class KafkaConsumerRepositoryMaker[DomainT: Deserializable]:
    """
    Context manager for Kafka consumer with distributed lock.

    `stream` decides what happens when the topic runs dry. Without it the consumer drains what
    is waiting and returns, which is what a periodic sync wants. With it the consumer stays on
    its partition indefinitely, and the cron that starts it becomes a supervisor rather than a
    schedule: every tick tries to start one, the lock turns all but the first away, and a tick
    only does anything once the running consumer has died. Recovery from a death that leaves
    the lock held (a killed worker) takes the lock's own `timeout`, so a streaming consumer
    wants that timeout measured in tens of seconds, not minutes.

    `stream_round_pause` is how long it waits between rounds — the topic's chance to refill,
    and the ceiling on how long a message can sit once it has arrived. A consumer whose topic
    trickles wants it longer, one whose latency is the point wants it short. It is bounded from
    above by the lock: pause plus poll timeout is the longest the lock can go unextended, and a
    pace that does not fit is refused at construction.

    Example:
        async with KafkaConsumerRepositoryMaker(
            consumer_class=EventConsumerRepository,
            partition=0,
            lock_class=RedisLock,
            lock_kwargs={'redis_client': redis_client, 'timeout': 300}
        ) as maker:
            async for batch in maker.get_batches():
                process(batch)
    """

    def __init__(
        self,
        consumer_class: type[BaseKafkaConsumerRepository[DomainT]],
        partition: int,
        lock_class: type[Lockable],
        lock_kwargs: dict[str, Any],
        stream: bool = False,
        stream_round_pause: timedelta = timedelta(seconds=1),
    ):
        lock_key = self.build_lock_key(consumer_class, partition)
        self.lock = lock_class(key=lock_key, **lock_kwargs)  # type: ignore[call-arg]
        self._consumer_class = consumer_class
        self._partition = partition
        self._stream = stream
        self._stream_round_pause = stream_round_pause

        if stream:
            self._check_beat_fits_lock()

    def _check_beat_fits_lock(self) -> None:
        """Refuse a pace that would let the lock die under a consumer that is still running.

        A streaming consumer beats once per round, and a round is the pause plus a poll that may
        wait its whole timeout out. Let that exceed the lock and the lock expires between beats:
        the next tick then starts a second consumer on the same partition, both read it and both
        commit, and nothing in the running system says so.
        """
        # The pause is only part of the gap: each round opens with a poll that waits its own
        # timeout out before the beat that follows it, and that timeout belongs to the consumer.
        poll_timeout = self._consumer_class.poll_timeout_ms / 1000
        beat_ceiling = self._stream_round_pause.total_seconds() + poll_timeout
        allowed = self.lock.timeout * MAX_BEAT_SHARE_OF_LOCK_TIMEOUT
        if beat_ceiling > allowed:
            raise ValueError(
                f'{self._consumer_class.__name__} streams with up to {beat_ceiling:g}s between lock '
                f'heartbeats (stream_round_pause {self._stream_round_pause.total_seconds():g}s + poll '
                f'timeout {poll_timeout:g}s), which does not fit the '
                f'{MAX_BEAT_SHARE_OF_LOCK_TIMEOUT:g} share of the lock timeout it is allowed '
                f'({allowed:g}s of {self.lock.timeout:g}s). Shorten the pause or raise the lock timeout.'
            )

    @staticmethod
    def build_lock_key(consumer_class: type[BaseKafkaConsumerRepository[Any]], partition: int) -> str:
        return f'{consumer_class.group_id}_{consumer_class.topic}_partition_{partition}'

    async def get_batches(self) -> AsyncIterator[tuple[DomainT, ...]]:
        while True:
            async for batch in self.consumer_repo.get_batches():
                yield batch
                await self.checkpoint()

            if not self._stream:
                return

            # The topic went quiet. Returning here would hand the partition back and leave the
            # next message to whatever starts a consumer again — a cron tick, and with it a
            # whole stage of the send path's latency. Instead the lock is kept alive and the
            # consumer asked once more: its own poll timeout is the wait, so an idle partition
            # costs one call every few seconds and a message is taken up as it lands.
            #
            # A checkpoint rather than a bare `extend`, so the heartbeat has one call site: the
            # one inside the batch loop runs per yielded batch, and a round that found nothing
            # yields none, so without this an idle partition would have no heartbeat at all —
            # the lock would expire under a consumer still running and the next tick would
            # start a second one on the same partition.
            await self.checkpoint()

            # A round ends either because the topic is empty or because the batch it found was
            # too thin to keep going — and the second one used to mean the run was over, with
            # the next cron tick giving the topic a minute to refill. Re-entering at once takes
            # that away, so the pause stands in for it: it lets records accumulate into fuller
            # batches, and it is the floor under a poll that returns instantly, which would
            # otherwise spin. Short enough to stay inside the latency this mode exists to save.
            await asyncio.sleep(self._stream_round_pause.total_seconds())

    async def checkpoint(self) -> None:
        await self.lock.extend()
        await self.consumer_repo.commit()

    async def _close(self) -> None:
        try:
            await self.consumer_repo.stop()
        finally:
            await self.lock.release()

    async def __aenter__(self) -> Self:
        await self.lock.acquire()

        self.consumer_repo = self._consumer_class(partition=self._partition)
        try:
            await self.consumer_repo.start()
        except Exception as e:  # noqa: BLE001
            await self._close()
            raise ConsumerStartError('Failed to start consumer') from e

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            await self.consumer_repo.commit()
        finally:
            await self._close()
