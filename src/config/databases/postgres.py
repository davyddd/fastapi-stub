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
    """Unit of work. The outermost block owns the transaction and, on exit, removes the task's
    session from the registry (which closes it), so nothing outlives the block. Nested blocks join."""

    session: AsyncSession | None
    in_transaction: bool | None

    def __init__(self):
        self.session = None
        self.in_transaction = None

    async def _initial(self):
        if self.session is None or self.in_transaction is None:
            self.session = await postgres_session_registry()
            self.in_transaction = self.session.in_transaction()

    async def __aenter__(self) -> AsyncSession:
        await self._initial()

        if not self.in_transaction:
            await self.session.begin()  # type: ignore

        return self.session  # type: ignore

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_value: Exception | None, traceback: Any) -> None:
        if self.in_transaction:
            return

        try:
            if exc_type is not None:
                await self.session.rollback()  # type: ignore
            else:
                await self.session.commit()  # type: ignore
        finally:
            await postgres_session_registry.clear()
