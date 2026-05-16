from collections.abc import AsyncIterator
from typing import Any, Protocol, Self

from share.kafka.consumer import BaseKafkaConsumerRepository, Deserializable


class Lockable(Protocol):
    async def acquire(self) -> None: ...

    async def release(self) -> None: ...

    async def extend(self) -> None: ...


class ConsumerStartError(Exception): ...


class KafkaConsumerRepositoryMaker[DomainT: Deserializable]:
    """
    Context manager for Kafka consumer with distributed lock.

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
    ):
        lock_key = self.build_lock_key(consumer_class, partition)
        self.lock = lock_class(key=lock_key, **lock_kwargs)  # type: ignore[call-arg]
        self._consumer_class = consumer_class
        self._partition = partition

    @staticmethod
    def build_lock_key(consumer_class: type[BaseKafkaConsumerRepository[Any]], partition: int) -> str:
        return f'{consumer_class.group_id}_{consumer_class.topic}_partition_{partition}'

    async def get_batches(self) -> AsyncIterator[tuple[DomainT, ...]]:
        async for batch in self.consumer_repo.get_batches():
            yield batch
            await self.checkpoint()

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
