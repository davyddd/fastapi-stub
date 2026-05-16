from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from redis.exceptions import RedisError


def suppress_redis_errors[T](func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T | None]]:
    """Decorator to suppress Redis exceptions and return None on failure."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T | None:
        try:
            return await func(*args, **kwargs)
        except RedisError:
            return None

    return wrapper
