from typing import Self

from redis.asyncio import Redis
from redis.asyncio.lock import Lock


class AlreadyAcquiredError(Exception):
    ...


class RedisLock:
    def __init__(self, redis_client: Redis, key: str, timeout: float = 10.0, blocking: bool = False):
        blocking_timeout = timeout if blocking else None
        self.timeout = timeout
        self.lock = Lock(
            redis=redis_client,
            name=key,
            timeout=timeout,
            blocking=blocking,
            blocking_timeout=blocking_timeout,
            thread_local=False,
        )

    async def acquire(self) -> None:
        acquired = await self.lock.acquire()

        if not acquired:
            raise AlreadyAcquiredError('Lock is already acquired')

    async def release(self) -> None:
        await self.lock.release()

    async def extend(self) -> None:
        await self.lock.extend(self.timeout)

    async def __aenter__(self) -> Self:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.release()
