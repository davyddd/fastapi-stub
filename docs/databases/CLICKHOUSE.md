## ClickHouse

### Models

ClickHouse models are **not** described in code.
Tables are created manually via [migrations](./MIGRATIONS.md) using native ClickHouse SQL (engines, partitions, TTL, etc.).

### Naming for materialized views

To make a table's role visible from its name alone:

- **`<name>_mv`** — target table that a materialized view writes into (typically `AggregatingMergeTree` / `ReplicatedAggregatingMergeTree`).
- **`<name>_trigger`** — the `MATERIALIZED VIEW ... TO <name>_mv` itself (it triggers on INSERT into the source table and pushes rows into the target).
- Source / buffer tables keep their domain name (often suffixed with `_raw` for `Null`-engine write buffers, e.g. `profile_raw`).

**Example:**
```sql
-- Source: Null-engine write buffer, MVs read from it
CREATE TABLE profile_raw ON CLUSTER '{cluster}' (...) ENGINE = Null;

-- Target: aggregating mat-view storage
CREATE TABLE segment_filter_meta_mv ON CLUSTER '{cluster}' (...) ENGINE = ReplicatedAggregatingMergeTree ...;

-- Trigger: MV that fires on INSERT into profile_raw and pushes to the _mv target
CREATE MATERIALIZED VIEW segment_filter_meta_profile_trigger ON CLUSTER '{cluster}'
TO segment_filter_meta_mv
AS SELECT ... FROM profile_raw WHERE ...;
```

### Queries

All queries use the `SQL` component with `.clickhouse` executor (see [RAW_SQL.md](./RAW_SQL.md) for details).

The `Query(model=...)` accepts any typed object: `TypedDict`, `DataTransferObject`, `ValueObject`, etc. 
Prefer using domain DTOs over `TypedDict` when the result is used beyond the repository.

**Example:**
```python
from datetime import datetime

from dddesign.structure.domains.dto import DataTransferObject
from dddesign.structure.infrastructure.repositories import Repository
from ddsql.query import Query

from config.databases.services.sql import SQL


class ProfileAnalytics(DataTransferObject):
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