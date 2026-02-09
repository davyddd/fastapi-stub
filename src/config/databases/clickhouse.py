import asyncio

from clickhouse_connect import create_async_client
from clickhouse_connect.driver import AsyncClient

from ddutils.scoped_registry import ScopedRegistry

from config.settings import settings


async def async_clickhouse_client_maker() -> AsyncClient:
    return await create_async_client(dsn=str(settings.CLICKHOUSE_URL))


clickhouse_client_registry: ScopedRegistry[AsyncClient] = ScopedRegistry[AsyncClient](
    create_func=async_clickhouse_client_maker, scope_func=asyncio.current_task, destructor_method_name='close'
)
