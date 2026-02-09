from typing import Optional, Set, TypedDict

from dddesign.structure.infrastructure.repositories import Repository
from ddsql.query import Query

from config.databases.services.sql import SQL


class DBVersion(TypedDict):
    version: str


query = Query(text='SELECT version() as version;', model=DBVersion)


class ProbeRepository(Repository):
    EXTERNAL_ALLOWED_METHODS: Optional[Set[str]] = {'get_pg_version', 'get_ch_version'}

    @staticmethod
    async def get_pg_version() -> Optional[str]:
        result = await SQL(query).postgres.execute()
        obj = result.get()
        return obj['version'] if obj else None

    @staticmethod
    async def get_ch_version() -> Optional[str]:
        result = await SQL(query).clickhouse.execute()
        obj = result.get()
        return obj['version'] if obj else None


probe_repository_impl = ProbeRepository()
