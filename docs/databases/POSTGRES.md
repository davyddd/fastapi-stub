## PostgreSQL

### Models

ORM models inherit from `BaseSQLModel` (located in `share/sqlmodel/models/base.py`).
This base class configures naming conventions for constraints
and auto-generates table names from class names using snake_case conversion.

PK field must follow the pattern `{entity}_id` (e.g., `profile_id`, `order_id`) and be `UUID` type.

For timestamp fields use `DatesMixin` (adds both `created_at` and `updated_at`),
or individual mixins `CreatedDateMixin` / `UpdatedDateMixin` if only one field is needed.

Project-wide column type helpers live under `share.sqlmodel.models.types.*` — one file per type.

**DateTime columns must use `DATETIME_TZ`** (`TIMESTAMP WITH TIME ZONE` in PostgreSQL).
Import `DATETIME_TZ` from `share.sqlmodel.models.types.datetime` and pass it via `Field(sa_type=DATETIME_TZ)`.
This ensures all timestamps are stored with timezone information.

**JSONB columns must use the `JSONB` helper** from `share.sqlmodel.models.types.json`,
not the raw `sqlalchemy.dialects.postgresql.JSONB`.
The shared instance is configured with `none_as_null=True`, so Python `None` is persisted as SQL `NULL`,
not as the JSON literal `null` (`'null'::jsonb`).
Without this flag, `instance.field = None` and `.values(field=None)` write JSON null,
which DataGrip shows as plain `null` (not `<null>`) and which `WHERE field IS NULL` does not match.
Always pass `nullable=True`/`nullable=False` explicitly on JSONB columns to mirror the type annotation
(`dict | None` → `nullable=True`, `dict` → `nullable=False`) and pair the usage with `# type: ignore[arg-type]`,
the same pattern used for `DATETIME_TZ`.

```python
from share.sqlmodel.models.types.json import JSONB

class CampaignModel(BaseSQLModel[Campaign], DatesMixin, table=True):
    sequence_plan: dict | None = Field(default=None, sa_type=JSONB, nullable=True)  # type: ignore[arg-type]
    stop_events: list = Field(default_factory=list, sa_type=JSONB, nullable=False)  # type: ignore[arg-type]
```

**Foreign keys must not cross context boundaries.** `Field(foreign_key='<table>.<column>')`
is only allowed when the referenced table lives in the same `<context>_context` package as the
declaring model. Cross-context references stay as bare-UUID columns (e.g. `project_id: UUID`)
with no `foreign_key=` argument; referential integrity is enforced at the application layer.
This mirrors the Python-level rule from [IMPORTS.md](../conventions/IMPORTS.md) (contexts must
not import each other) at the database level, so each context keeps its schema independent and
can later be extracted into a separate service without DDL surgery.

`BaseSQLModel` is generic and provides base implementations of `to_entity()` and `from_entity()`.
Specify the entity type as a generic parameter: `BaseSQLModel[YourEntity]`.
`to_entity(**extra_fields)` forwards extra keyword arguments into the entity — use it for
entity fields that are not model columns (e.g. a computed SELECT expression):
`instance.to_entity(state=state)` for rows shaped as `(instance, state)`.
Override the methods only when custom mapping is required (e.g., field renaming, value objects wrapping).

Migrations are auto-generated from model definitions — see [MIGRATIONS.md](./MIGRATIONS.md).

**Example:**
```python
from datetime import datetime
from uuid import UUID

from sqlmodel import Field

from share.sqlmodel.models.base import BaseSQLModel
from share.sqlmodel.models.mixins.dates import DatesMixin
from share.sqlmodel.models.types.datetime import DATETIME_TZ

from app.profile_context.domains.entities.profile import Profile


class ProfileModel(BaseSQLModel[Profile], DatesMixin, table=True):
    profile_id: UUID = Field(primary_key=True)
    first_name: str | None
    last_name: str | None
    email: str
    registered_at: datetime = Field(sa_type=DATETIME_TZ)  # type: ignore[arg-type]
    expires_at: datetime | None = Field(default=None, sa_type=DATETIME_TZ)  # type: ignore[arg-type]
```

### Queries

Simple CRUD operations use ORM via `SQLModel` in repositories.

**Example:**
```python
from dddesign.structure.infrastructure.repositories import Repository
from ddutils.datetime_helpers import utc_now
from sqlmodel import select, update

from config.databases.postgres import postgres_session_factory


class ProfileRepository(Repository):
    async def get(self, profile_id: ProfileId) -> Profile | None:
        async with postgres_session_factory() as session:
            instance = await session.get(ProfileModel, profile_id)
            return instance.to_entity() if instance else None

    async def create(self, profile: Profile) -> None:
        async with postgres_session_factory() as session:
            instance = ProfileModel.from_entity(profile)
            session.add(instance)
            await session.flush()

    async def update(self, entity: Profile) -> None:
        if not entity.has_changed:
            return

        async with postgres_session_factory() as session:
            statement = (
                update(ProfileModel)
                .where(ProfileModel.profile_id == entity.profile_id)
                .values(**entity.changed_data, updated_at=utc_now())
            )
            await session.execute(statement)
```

**Insert-or-skip (`ON CONFLICT DO NOTHING`).** When the caller must know whether the row was
actually written — to publish an event, to fall back to an update — read `RETURNING`, never
`result.rowcount`. Through the async driver an `insert(...).values(...)` reports no row count at
all (`-1`, which is truthy), on a real insert and on a skipped duplicate alike, so
`bool(result.rowcount)` says "inserted" every time. `RETURNING` is empty exactly when nothing was
written. `rowcount` is fine after `UPDATE` / `DELETE`.

**Example:**
```python
statement = (
    insert(TransactionEventModel)
    .values(**instance.model_dump(exclude={'created_at', 'updated_at'}))
    .on_conflict_do_nothing()
    .returning(TransactionEventModel.transaction_event_id)
)
result = await session.execute(statement)
return result.first() is not None
```

For list endpoints with filtering, search, ordering, and pagination see [PAGINATION.md](../conventions/PAGINATION.md).

For complex queries (joins, aggregations) use raw SQL via `ddsql`. 
More details on SQL queries see in [RAW_SQL.md](./RAW_SQL.md).

**Example:**
```python
from typing import TypedDict

from dddesign.structure.infrastructure.repositories import Repository
from ddsql.query import Query

from config.databases.services.sql import SQL


class ProfileWithStats(TypedDict):
    profile_id: int
    name: str
    subscription_count: int


query = Query(
    model=ProfileWithStats,
    text='''
        SELECT
            p.profile_id,
            p.name,
            COUNT(s.id) as subscription_count
        FROM profile p
        LEFT JOIN subscription s ON
            s.profile_id = p.profile_id
        WHERE
            p.profile_id IN {{ serialize_value(profile_ids) }}
        GROUP BY p.profile_id, p.name
    ''',
)


class ProfileStatsRepository(Repository):
    @staticmethod
    async def get(profile_id: ProfileId) -> ProfileWithStats | None:
        result = await SQL(query).with_params(profile_ids=[profile_id]).postgres.execute()
        return result.get()

    @staticmethod
    async def get_list(profile_ids: list[ProfileId]) -> list[ProfileWithStats]:
        result = await SQL(query).with_params(profile_ids=profile_ids).postgres.execute()
        return result.get_list()


profile_stats_repository_impl = ProfileStatsRepository()
```

### Transactions

As shown above, all operations use the `postgres_session_factory()` context manager from `config.databases.postgres`: a `ConnectionManagerFactory` from `ddsql.connections` over the per-connection session registries, opening the project `PostgresConnectionManager` (a unit of work).

`postgres_session_factory()` supports nested calls — if a transaction is already active,
it reuses the existing session without starting a new transaction.
The outermost `postgres_session_factory()` block controls the commit/rollback and, on exit, closes the session:
nothing outlives the block, there is no cleanup to do elsewhere.

The session is bound to `asyncio.current_task()`, so an `postgres_session_factory()` inside a coroutine spawned via
`asyncio.gather` or `TaskGroup` **does not join the caller's transaction** — it gets its own session
and transaction, committed independently. Keep concurrent children read-only or make each child's
write self-contained.

### Connections (read replica)

`postgres_session_factory(alias=...)` picks the database like Django's `using`. `PostgresConnectionAlias.PRIMARY` is the default;
`PostgresConnectionAlias.REPLICA` reads from `POSTGRES_REPLICA_URL` and falls back to `POSTGRES_URL` when it is
not set, so code written for the replica works locally without one. Each connection has its own engine,
pool and session registry: a replica block inside a primary block opens a separate session and
transaction, it does not join the writing one.

```python
async with postgres_session_factory(alias=PostgresConnectionAlias.REPLICA) as session:
    result = await session.execute(statement)
```

Raw SQL picks the database right before executing: `SQL(query).postgres.using(PostgresConnectionAlias.REPLICA).execute()`.

Reading from the replica is a decision of the use case, not of the repository: it is right for reports,
listings and periodic jobs that tolerate replication lag, and wrong right after a write in the same flow,
where the replica may not have the row yet. Writes against the replica are rejected by the standby itself.

Connections come from a client-side pool in front of Odyssey (`POOL_*` constants in
`config.databases.postgres`): a transaction leases a connection and returns it on commit/rollback,
the TCP connection stays open for the next one.

`postgres_session_factory()` can be used at the Application layer to achieve atomicity across multiple Applications.
This is allowed to keep Repositories simple — they work with single Entities, not Aggregates for state mutations.

**Example:**

```python
from dddesign.structure.applications import Application

from config.databases.postgres import postgres_session_factory


class OrderApp(Application):
    payment_app: PaymentApp
    inventory_app: InventoryApp

    async def create(self, data: CreateOrderDTO) -> Order:
        async with postgres_session_factory():
            order = Order.factory(data)
            await self.payment_app.charge(order.profile_id, order.total)
            await self.inventory_app.reserve(order.items)
            return order
```