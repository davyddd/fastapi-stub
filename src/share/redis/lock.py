import contextlib
from typing import Self

from redis.asyncio import Redis
from redis.asyncio.lock import Lock, LockNotOwnedError


class AlreadyAcquiredError(Exception): ...


class RedisLock:
    """
    Distributed lock backed by Redis (`SET NX PX` + Lua release).

    Caveat: `timeout` is the Redis-side TTL of the key — not a client-side cancellation
    timer. If the protected code runs longer than `timeout`, Redis silently removes the
    key and a competing caller can acquire the same lock and execute in parallel,
    violating mutual exclusion. The original code keeps running unaware. `release()`
    swallows `LockNotOwnedError` for this case, so the cleanup is silent — but the
    invariant has already been broken upstream.

    To avoid this, either pick a `timeout` that comfortably exceeds the worst-case
    runtime of the block, or call `extend()` periodically (heartbeat) for long
    operations whose duration is hard to predict.
    """

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
        with contextlib.suppress(LockNotOwnedError):
            await self.lock.release()

    async def extend(self) -> None:
        await self.lock.extend(self.timeout)

    async def __aenter__(self) -> Self:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.release()
