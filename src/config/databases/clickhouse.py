import os
from functools import partial

from clickhouse_connect import create_async_client
from clickhouse_connect.driver import AsyncClient

from dddesign.structure.domains.constants import BaseEnum
from ddsql.connections import ConnectionManager, ConnectionManagerFactory
from ddutils.scoped_registry import ScopedRegistry

from config.settings import settings

# Concurrent queries per process. Matches the urllib3 pool size of the client (8), so under load
# no connection is opened just to be dropped.
EXECUTOR_THREADS = 8


class ClickhouseConnectionAlias(str, BaseEnum):
    """Cluster to run a query against, chosen per call like Postgres' `postgres_session_factory(alias=...)`."""

    PRIMARY = 'primary'

    @property
    def url(self) -> str:
        urls = {
            ClickhouseConnectionAlias.PRIMARY: settings.CLICKHOUSE_URL,
        }
        return str(urls[self])


async def _create_client(alias: ClickhouseConnectionAlias) -> AsyncClient:
    return await create_async_client(dsn=alias.url, executor_threads=EXECUTOR_THREADS)


def _build_client_registry(alias: ClickhouseConnectionAlias) -> ScopedRegistry[AsyncClient]:
    # One client per process, nobody clears it. `AsyncClient` is itself a pool: a urllib3 connection
    # pool plus a ThreadPoolExecutor that runs the queries, and it carries no per-task state
    # (`create_async_client` leaves `autogenerate_session_id` off, so concurrent queries never share a
    # ClickHouse session).
    return ScopedRegistry[AsyncClient](
        create_func=partial(_create_client, alias), scope_func=os.getpid, destructor_method_name='close'
    )


clickhouse_client_registries: dict[ClickhouseConnectionAlias, ScopedRegistry[AsyncClient]] = {
    alias: _build_client_registry(alias) for alias in ClickhouseConnectionAlias
}


# `async with clickhouse_client_factory() as client`, or `(alias=ClickhouseConnectionAlias.PRIMARY)` to pick the cluster;
# the default `ConnectionManager` hands out the process-wide client and closes nothing on exit
clickhouse_client_factory: ConnectionManagerFactory[ClickhouseConnectionAlias, AsyncClient, ConnectionManager[AsyncClient]] = (
    ConnectionManagerFactory(
        clickhouse_client_registries,
        default=ClickhouseConnectionAlias.PRIMARY,
        connection_manager_class=ConnectionManager[AsyncClient],
    )
)
