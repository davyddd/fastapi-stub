import os

from clickhouse_connect import create_async_client
from clickhouse_connect.driver import AsyncClient

from ddutils.scoped_registry import ScopedRegistry

from config.settings import settings

# Concurrent queries per process. Matches the urllib3 pool size of the client (8), so under load
# no connection is opened just to be dropped.
EXECUTOR_THREADS = 8


async def async_clickhouse_client_maker() -> AsyncClient:
    return await create_async_client(dsn=str(settings.CLICKHOUSE_URL), executor_threads=EXECUTOR_THREADS)


# One client per process, nobody clears it. `AsyncClient` is itself a pool: a urllib3 connection
# pool plus a ThreadPoolExecutor that runs the queries, and it carries no per-task state
# (`create_async_client` leaves `autogenerate_session_id` off, so concurrent queries never share a
# ClickHouse session).
clickhouse_client_registry: ScopedRegistry[AsyncClient] = ScopedRegistry[AsyncClient](
    create_func=async_clickhouse_client_maker, scope_func=os.getpid, destructor_method_name='close'
)
