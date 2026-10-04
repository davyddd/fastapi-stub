import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool
from sqlmodel.ext.asyncio.session import AsyncSession

from dddesign.structure.domains.constants import BaseEnum
from ddsql.connections import ConnectionManager, ConnectionManagerFactory
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


class PostgresConnectionAlias(str, BaseEnum):
    """Database to run a transaction against, chosen per `postgres_session_factory()` block like Django's `using`."""

    PRIMARY = 'primary'
    REPLICA = 'replica'  # read-only; writes are rejected by the standby itself

    @property
    def url(self) -> str:
        urls = {
            PostgresConnectionAlias.PRIMARY: settings.POSTGRES_URL,
            # falls back to the primary when no replica is configured (local, tests)
            PostgresConnectionAlias.REPLICA: settings.POSTGRES_REPLICA_URL or settings.POSTGRES_URL,
        }
        return str(urls[self])


def _build_session_registry(alias: PostgresConnectionAlias) -> ScopedRegistry[AsyncSession]:
    engine = create_async_engine(
        alias.url,
        poolclass=AsyncAdaptedQueuePool,
        pool_size=POOL_SIZE,
        max_overflow=POOL_MAX_OVERFLOW,
        pool_recycle=POOL_RECYCLE,
        connect_args={'prepare_threshold': None},
    )
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, autocommit=False, autoflush=False, autobegin=False)
    # One session per task: a session drives one connection and one transaction, neither of which can
    # be shared by concurrent tasks. A gather/TaskGroup child therefore gets its own session and does
    # not join the caller's transaction. The outermost `postgres_session_factory()` block of a task is the manager of its entry.
    return ScopedRegistry[AsyncSession](
        create_func=session_maker, scope_func=asyncio.current_task, destructor_method_name='close'
    )


# Each alias has its own pool, so the Odyssey budget above is per alias
postgres_session_registries: dict[PostgresConnectionAlias, ScopedRegistry[AsyncSession]] = {
    alias: _build_session_registry(alias) for alias in PostgresConnectionAlias
}


class SessionManager(ConnectionManager[AsyncSession]):
    """Unit of work on a Postgres session, opened by `postgres_session_factory()`.

    Unlike the base manager, which only hands out the registry's connection, the outermost block owns the
    transaction and the registry scope: on exit it commits or rolls back and leaves the scope, which removes
    the task's session from the registry and closes it, so nothing outlives the block. Nested blocks on the
    same database join the session and the transaction; a block on another database opens its own.
    """

    session: AsyncSession | None
    in_transaction: bool | None

    def __init__(self, registry: ScopedRegistry[AsyncSession]) -> None:
        super().__init__(registry)
        self._scope = registry.scope()
        self.session = None
        self.in_transaction = None

    async def __aenter__(self) -> AsyncSession:
        session = await self._scope.__aenter__()
        self.session = session
        self.in_transaction = session.in_transaction()

        if not self.in_transaction:
            await session.begin()

        return session

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: Any) -> None:
        try:
            if self.session is not None and not self.in_transaction:
                if exc_type is not None:
                    await self.session.rollback()
                else:
                    await self.session.commit()
        finally:
            await self._scope.__aexit__(exc_type, exc_value, traceback)


# `async with postgres_session_factory() as session`, or `(alias=PostgresConnectionAlias.REPLICA)` to pick the database
postgres_session_factory: ConnectionManagerFactory[PostgresConnectionAlias, AsyncSession, SessionManager] = (
    ConnectionManagerFactory(
        postgres_session_registries,
        default=PostgresConnectionAlias.PRIMARY,
        connection_manager_class=SessionManager,
    )
)
