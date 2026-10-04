import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool
from sqlmodel.ext.asyncio.session import AsyncSession

from ddutils.scoped_registry import ScopedRegistry

from config.settings import settings

# Client-side pool in front of Odyssey: a transaction leases a connection and returns it on
# commit/rollback, and the TCP connection stays open for the next one instead of being reopened.
# size + overflow must cover the worker's concurrency (runworker --threads 20); the total per
# deployment is (size + overflow) x processes, keep it under Odyssey's client_max.
POOL_SIZE = 5
POOL_MAX_OVERFLOW = 15
POOL_RECYCLE = 1800  # seconds, keep below Odyssey's client idle timeout
# Disable prepared statements (prepare_threshold=None) because Odyssey connection pooler
# uses transaction pooling mode with pool_discard=no — prepared statements are bound
# to a specific backend connection and break when the pooler assigns a different one.
# Alternative server-side fix: set pool_discard=yes in Odyssey to send DISCARD ALL
# on connection release, but that adds a roundtrip per transaction.
postgres_engine = create_async_engine(
    str(settings.POSTGRES_URL),
    poolclass=AsyncAdaptedQueuePool,
    pool_size=POOL_SIZE,
    max_overflow=POOL_MAX_OVERFLOW,
    pool_recycle=POOL_RECYCLE,
    connect_args={'prepare_threshold': None},
)


async_postgres_session_maker = async_sessionmaker(
    bind=postgres_engine, class_=AsyncSession, autocommit=False, autoflush=False, autobegin=False
)

# One session per task: a session drives one connection and one transaction, neither of which can
# be shared by concurrent tasks. A gather/TaskGroup child therefore gets its own session and does
# not join the caller's transaction. The outermost `Atomic` of a task is the manager of its entry.
postgres_session_registry: ScopedRegistry[AsyncSession] = ScopedRegistry[AsyncSession](
    create_func=async_postgres_session_maker, scope_func=asyncio.current_task, destructor_method_name='close'
)


class Atomic:
    """Unit of work. The outermost block owns the transaction and the registry scope: on exit it commits or
    rolls back and leaves the scope, which removes the task's session from the registry and closes it, so
    nothing outlives the block. Nested blocks join the session and the transaction."""

    session: AsyncSession | None
    in_transaction: bool | None

    def __init__(self):
        self._scope = postgres_session_registry.scope()
        self.session = None
        self.in_transaction = None

    async def __aenter__(self) -> AsyncSession:
        self.session = await self._scope.__aenter__()
        self.in_transaction = self.session.in_transaction()

        if not self.in_transaction:
            await self.session.begin()

        return self.session

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: Any) -> None:
        try:
            if self.session is not None and not self.in_transaction:
                if exc_type is not None:
                    await self.session.rollback()
                else:
                    await self.session.commit()
        finally:
            await self._scope.__aexit__(exc_type, exc_value, traceback)
