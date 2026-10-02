import time
import uuid
from contextvars import ContextVar
from typing import Any

from pydantic import Field, computed_field

from dddesign.structure.domains.value_objects import ValueObject
from ddutils.scoped_registry import ScopedRegistry


class Headers(ValueObject):
    ip_address: str | None = Field(None, alias='x-forwarded-for')
    domain: str | None = Field(None, alias='host')


class LogProperties(ValueObject):
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    start_time: float = Field(default_factory=time.time, exclude=True)
    headers: Headers | None = None

    @computed_field(return_type=float)
    def duration(self) -> float:
        return round(time.time() - self.start_time, 3)


async def _create_log_properties(**kwargs: Any) -> LogProperties:
    return LogProperties.model_validate(kwargs)


_execution_key: ContextVar[object | None] = ContextVar('log_properties_execution_key', default=None)


def _execution_scope() -> object:
    """Scope of one execution (HTTP request, actor run), not of one task.

    The key is set in the execution context on first use and inherited by every coroutine spawned
    inside it, so a gather/TaskGroup child logs with the request_id of its parent. The registry
    entry is removed by `LogPropertiesManagerMiddleware.clear()` at the end of the execution.
    """
    key = _execution_key.get()
    if key is None:
        key = object()
        _execution_key.set(key)
    return key


log_properties_registry: ScopedRegistry[LogProperties] = ScopedRegistry[LogProperties](
    create_func=_create_log_properties, scope_func=_execution_scope
)
