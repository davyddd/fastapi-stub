## ClickHouse

### Models

ClickHouse models are **not** described in code.
Tables are created manually via [migrations](./MIGRATIONS.md) using native ClickHouse SQL (engines, partitions, TTL, etc.).

### Queries

All queries use the `SQL` component with `.clickhouse` executor (see [RAW_SQL.md](./RAW_SQL.md) for details).

**Example:**
```python
from datetime import datetime
from typing import TypedDict

from dddesign.structure.infrastructure.repositories import Repository
from ddsql.query import Query

from config.databases.services.sql import SQL


class ProfileAnalytics(TypedDict):
    profile_id: int
    total_events: int
    last_event_at: datetime


query = Query(
    model=ProfileAnalytics,
    text='''
        SELECT
            profile_id,
            count() as total_events,
            max(created_at) as last_event_at
        FROM events
        WHERE
            profile_id IN {{ serialize_value(profile_ids) }}
        GROUP BY profile_id
    ''',
)


class ProfileAnalyticsRepository(Repository):
    @staticmethod
    async def get(profile_id: ProfileId) -> ProfileAnalytics | None:
        result = await SQL(query).with_params(profile_ids=[profile_id]).clickhouse.execute()
        return result.get()

    @staticmethod
    async def get_list(profile_ids: list[ProfileId]) -> list[ProfileAnalytics]:
        result = await SQL(query).with_params(profile_ids=profile_ids).clickhouse.execute()
        return result.get_list()


profile_analytics_repository_impl = ProfileAnalyticsRepository()
```