import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool.impl import NullPool
from sqlmodel.ext.asyncio.session import AsyncSession

from ddutils.scoped_registry import ScopedRegistry

from config.settings import settings

postgres_engine = create_async_engine(str(settings.POSTGRES_URL), poolclass=NullPool)


async_postgres_session_maker = async_sessionmaker(
    bind=postgres_engine, class_=AsyncSession, autocommit=False, autoflush=False, autobegin=False
)

postgres_session_registry: ScopedRegistry[AsyncSession] = ScopedRegistry[AsyncSession](
    create_func=async_postgres_session_maker, scope_func=asyncio.current_task, destructor_method_name='close'
)


class Atomic:
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

        if exc_type is not None:
            await self.session.rollback()  # type: ignore
        else:
            await self.session.commit()  # type: ignore
