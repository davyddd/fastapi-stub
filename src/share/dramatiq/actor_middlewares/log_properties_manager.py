from collections.abc import Awaitable, Callable
from typing import Any

from ddutils.scoped_registry import ScopedRegistry

from share.dramatiq.actor_middlewares.base import BaseActorMiddleware


class LogPropertiesManagerMiddleware(BaseActorMiddleware):
    def __init__(self, log_properties_registry: ScopedRegistry):
        self.log_properties_registry = log_properties_registry

    async def __call__(self, call_next: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
        async with self.log_properties_registry.scope():
            return await call_next(*args, **kwargs)
