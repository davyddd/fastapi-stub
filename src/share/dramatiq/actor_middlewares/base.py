from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any


class BaseActorMiddleware(ABC):
    @abstractmethod
    async def __call__(self, call_next: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any: ...

    def wrap(self, func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await self(func, *args, **kwargs)

        return wrapper
