import asyncio

from config.databases.clickhouse import clickhouse_client_registry
from config.databases.postgres import postgres_session_registry


async def close_db_connections(*id_tasks: asyncio.Task):
    await clickhouse_client_registry.clear(*id_tasks)
    await postgres_session_registry.clear(*id_tasks)
