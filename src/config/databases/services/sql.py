from typing import Any

from sqlalchemy import text

from ddsql.adapter import Adapter, AdapterDescriptor
from ddsql.serializers.clickhouse import ClickhouseSerializer
from ddsql.serializers.postgres import PostgresSerializer
from ddsql.sqlbase import SQLBase

from config.databases.clickhouse import clickhouse_client_registry
from config.databases.postgres import Atomic


class PostgresAdapter(Adapter):
    serializer: PostgresSerializer = PostgresSerializer()

    async def _execute(self) -> list[dict[str, Any]]:
        async with Atomic() as postgres_session:
            query = await self.get_query()
            result = await postgres_session.execute(text(query))  # ty: ignore[deprecated]
            return [dict(zip(result.keys(), row)) for row in result.fetchall()]


class ClickhouseAdapter(Adapter):
    serializer: ClickhouseSerializer = ClickhouseSerializer()

    async def _execute(self) -> list[dict[str, Any]]:
        client = await clickhouse_client_registry()
        query = await self.get_query()
        result = await client.query(query)
        return [dict(zip(result.column_names, row)) for row in result.result_rows]


class SQL(SQLBase):
    postgres: PostgresAdapter = AdapterDescriptor(adapter_class=PostgresAdapter)  # type: ignore
    clickhouse: ClickhouseAdapter = AdapterDescriptor(adapter_class=ClickhouseAdapter)  # type: ignore
