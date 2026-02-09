from typing import Any, AsyncIterator, Generic, Protocol, Self

from share.kafka.consumer import BaseKafkaConsumerRepository, DomainT


class Lockable(Protocol):
    async def acquire(self) -> None:
        ...

    async def release(self) -> None:
        ...

    async def extend(self) -> None:
        ...


class ConsumerStartError(Exception):
    ...


class KafkaConsumerRepositoryMaker(Generic[DomainT]):
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
        self.consumer_repo = consumer_class(partition=partition)

    @staticmethod
    def build_lock_key(consumer_class: type[BaseKafkaConsumerRepository[Any]], partition: int) -> str:
        return f'{consumer_class.topic}_partition_{partition}'

    async def get_batches(self) -> AsyncIterator[tuple[DomainT, ...]]:
        try:
            async for batch in self.consumer_repo.get_batches():
                yield batch
                await self.checkpoint()
        except Exception:  # noqa: BLE001
            pass

    async def checkpoint(self) -> None:
        await self.lock.extend()
        await self.consumer_repo.commit()

    async def __aenter__(self) -> Self:
        await self.lock.acquire()

        try:
            await self.consumer_repo.start()
        except Exception as e:  # noqa: BLE001
            await self.lock.release()
            raise ConsumerStartError('Failed to start consumer') from e

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            await self.consumer_repo.commit()
            await self.consumer_repo.stop()
        finally:
            await self.lock.release()
