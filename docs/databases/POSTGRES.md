## PostgreSQL

### Models

ORM models inherit from `BaseSQLModel` (located in `share/sqlmodel/models/base.py`).
This base class configures naming conventions for constraints
and auto-generates table names from class names using snake_case conversion.

PK field must follow the pattern `{entity}_id` (e.g., `profile_id`, `order_id`) and be `UUID` type.

For timestamp fields use `DatesMixin` (adds both `created_at` and `updated_at`),
or individual mixins `CreatedDateMixin` / `UpdatedDateMixin` if only one field is needed.

`BaseSQLModel` is generic and provides base implementations of `to_entity()` and `from_entity()`.
Specify the entity type as a generic parameter: `BaseSQLModel[YourEntity]`.
Override the methods only when custom mapping is required (e.g., field renaming, value objects wrapping).

Migrations are auto-generated from model definitions — see [MIGRATIONS.md](./MIGRATIONS.md).

**Example:**
```python
from uuid import UUID

from sqlmodel import Field

from share.sqlmodel.models.base import BaseSQLModel
from share.sqlmodel.models.mixins.dates import DatesMixin

from app.profile_context.domains.entities.profile import Profile


class ProfileModel(BaseSQLModel[Profile], DatesMixin, table=True):
    profile_id: UUID = Field(primary_key=True)
    first_name: str | None
    last_name: str | None
    email: str
```

### Queries

Simple CRUD operations use ORM via `SQLModel` in repositories.

**Example:**
```python
from dddesign.structure.infrastructure.repositories import Repository
from sqlmodel import select

from config.databases.postgres import Atomic


class ProfileRepository(Repository):
    async def get(self, profile_id: ProfileId) -> Profile | None:
        async with Atomic() as session:
            instance = await session.get(ProfileModel, profile_id)
            return instance.to_entity() if instance else None

    async def create(self, profile: Profile) -> None:
        async with Atomic() as session:
            instance = ProfileModel.from_entity(profile)
            session.add(instance)
            await session.flush()
```

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

As shown above, all operations use `Atomic` context manager from `config.databases.postgres`.

`Atomic` supports nested calls — if a transaction is already active,
it reuses the existing session without starting a new transaction.
The outermost `Atomic` block controls the commit/rollback.

`Atomic` can be used at the Application layer to achieve atomicity across multiple Applications.
This is allowed to keep Repositories simple — they work with single Entities, not Aggregates for state mutations.

**Example:**

```python
from dddesign.structure.applications import Application

from config.databases.postgres import Atomic


class OrderApp(Application):
    payment_app: PaymentApp
    inventory_app: InventoryApp

    async def create(self, data: CreateOrderDTO) -> Order:
        async with Atomic():
            order = Order.factory(data)
            await self.payment_app.charge(order.profile_id, order.total)
            await self.inventory_app.reserve(order.items)
            return order
```