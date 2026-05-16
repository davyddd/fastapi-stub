from typing import TypedDict

from dddesign.structure.infrastructure.repositories import Repository
from ddsql.query import Query

from config.databases.services.sql import SQL


class DBVersion(TypedDict):
    version: str


query = Query(text='SELECT version() as version;', model=DBVersion)


class ProbeRepository(Repository):
    EXTERNAL_ALLOWED_METHODS: set[str] | None = {'get_pg_version', 'get_ch_version'}

    @staticmethod
    async def get_pg_version() -> str | None:
        result = await SQL(query).postgres.execute()
        obj = result.get()
        return obj['version'] if obj else None

    @staticmethod
    async def get_ch_version() -> str | None:
        result = await SQL(query).clickhouse.execute()
        obj = result.get()
        return obj['version'] if obj else None


probe_repository_impl = ProbeRepository()
