## Filtering & filtered updates

Data-access query contracts. Each model declares **once, in its repository module**, what
can be asked of it: filterable fields (with lookups), ordering fields, searchable fields,
range. This layer knows nothing about HTTP — list endpoints wrap the same contract into
a `QueryParams` at the route (see [PAGINATION.md](./PAGINATION.md)).

### Components

| Component | Path | Purpose |
|---|---|---|
| `Lookup` / `FieldLookups` | `share.sqlmodel.lookups` | Declared lookups for filter fields (`EXACT`, `IN`, `ISNULL`) |
| `SearchType` | `share.sqlmodel.lookups` | Search type enum (`ILIKE`, `EXACT`) |
| `FilterParams` | `share.sqlmodel.filter_params` | Query contract of a model: filters, ordering, search, range |
| `UpdateParams` | `share.sqlmodel.update_params` | Contract of columns a repository allows to update |
| `FilterSet` | `share.sqlmodel.filter_set` | Executes the contracts: paged SELECT, COUNT, filtered UPDATE |

### Declaring the contract

The contract lives in the repository module itself (`infrastructure/repositories/<r>.py`),
right above the Repository class — the contract and the implementation are read together.
The declaration lists the fields; each field states its allowed lookups with the
`FieldLookups` annotation (no marker — `EXACT` only). `FilterParams.build` expands every
declared lookup into its own concrete field and pins ordering/search capabilities:

```python
from typing import Annotated

from dddesign.structure.domains.dto import DataTransferObject

from share.sqlmodel.filter_params import FilterParams
from share.sqlmodel.lookups import FieldLookups, Lookup, SearchType


class CampaignFilters(DataTransferObject):
    campaign_id: Annotated[CampaignId | None, FieldLookups(Lookup.IN)] = None
    state: Annotated[CampaignStateEnum | None, FieldLookups(Lookup.IN)] = None


CampaignFilterParams = FilterParams.build(
    'CampaignFilterParams',
    filters=CampaignFilters,
    ordering_fields=('created_at',),
    default_ordering='-created_at',
    search_fields={'name': SearchType.ILIKE},
)
```

| Declaration | Generated field | SQL |
|---|---|---|
| `state: Annotated[State \| None, FieldLookups(Lookup.IN)]` | `state__in: list[State] \| None` | `state IN (...)` |
| `email: Annotated[str \| None, FieldLookups(Lookup.ISNULL)]` | `email__isnull: bool \| None` | `email IS [NOT] NULL` |
| `file_type: FileType \| None` (no marker) | `file_type: FileType \| None` | `file_type = ...` |

A field with the marker gets only the listed lookups — add `Lookup.EXACT` explicitly to
keep the bare field. List values are accepted only through an `IN` lookup: a bare field
receiving a list raises.

Every `FilterParams` instance also carries the query fields `ordering` (defaults to
`default_ordering`, validated against `ordering_fields`), `search`, `limit`, `page` and
`cursor`; `offset` and `page_size` are derived properties. `values` returns the
non-empty **filter** fields only.

Internal callers (adapters, applications) construct the contract directly — no HTTP
artifacts involved:

```python
campaigns, _, _ = await self.campaign_app.get_list(
    project_id,
    CampaignFilterParams(campaign_id__in=campaign_ids, limit=max(len(campaign_ids), MAX_LIMIT)),
)
```

### FilterSet

`FilterSet` executes the contract against the database — repositories hand it a session
and a base statement and get domain-ready results back:

| Parameter | Type | Description |
|---|---|---|
| `session` | `AsyncSession` | Required; the surrounding `Atomic()` session |
| `model` | `type[SQLModel]` | SQLAlchemy model for column access |
| `base_statement` | `Select \| Update` | Base statement to extend |
| `params` | `FilterParams` | The contract instance |
| `extra_columns` | `dict[str, Any]` | Computed columns for filtering (e.g. `case` expressions) |

**Methods (all async, all executing):**
- `select()` — one page of objects plus both boundary cursors:
  `(rows, next_cursor, prev_cursor)`. Model instances when a single entity is selected,
  raw rows otherwise. Every list is keyset-capable — see below.
- `count()` — the number of matching rows (filters + search)
- `update_by_filters(update_params)` — SET from `UpdateParams`, WHERE from the filter
  fields of `params`; expects an Update `base_statement`

```python
class CampaignRepository(Repository):
    @classmethod
    async def get_list(
        cls, project_id: ProjectId, params: CampaignFilterParams
    ) -> tuple[list[Campaign], str | None, str | None]:
        statement, extra_columns = _build_base_statement()
        statement = statement.where(CampaignModel.project_id == project_id)

        async with Atomic() as session:
            filter_set = FilterSet(
                session=session, model=CampaignModel, params=params, base_statement=statement, extra_columns=extra_columns
            )
            rows, next_cursor, prev_cursor = await filter_set.select()
            # Convert inside the session: leaving Atomic commits and expires ORM instances.
            # `to_entity(**extra_fields)` forwards computed columns into the entity.
            entities = [instance.to_entity(state=state) for instance, state in rows]
        return entities, next_cursor, prev_cursor
```

### Keyset paging inside `select()`

There is nothing extra to declare: the cursor's composite key is always **the effective
ordering plus the model's primary key** as a unique tiebreaker. The opaque `cursor`
value (a query field on `FilterParams`) carries the boundary-row key and the paging
direction; `prev` cursors scan in reverse and are flipped back to display order.

- With `params.cursor` — the fast keyset path (anchor predicate over the composite key).
- Without one — `OFFSET (page - 1) * page_size` fallback for arbitrary page jumps.
- One extra row is over-fetched: it signals continuation on the scan side; the other
  side is implied by how we got here (a cursor, or a jump past page 1).
- A malformed cursor, or one built for a different ordering, raises `ValueError` — map
  it to the domain error at the application layer.

The key is pinned by the declaration — e.g. for the Users list:

```python
ProfileListFilterParams = FilterParams.build(
    'ProfileListFilterParams',
    ordering_fields=('created_at',),
    default_ordering='-created_at',  # keyset key becomes (-created_at, profile_id)
    search_fields={...},
)
```

`SearchType.EXACT` coerces the search term into the column type (e.g. UUID); an
uncastable term skips that column instead of erroring.

### Filtered UPDATE

An `UpdateParams` subclass (same repository module) declares what can be updated;
the application decides which fields to fill (`None` fields are skipped, an empty SET
raises):

```python
class TransactionEventUpdateFilters(DataTransferObject):
    external_profile_id: str | None = None
    source: ProfileSource | None = None
    email: Annotated[str | None, FieldLookups(Lookup.ISNULL)] = None


TransactionEventUpdateFilterParams = FilterParams.build(
    'TransactionEventUpdateFilterParams',
    filters=TransactionEventUpdateFilters,
)


class TransactionEventUpdateParams(UpdateParams):
    scheduled_email_id: ScheduledEmailId | None = None
    email: str | None = None
```

```python
class TransactionEventRepository(Repository):
    @staticmethod
    async def update_by_filters(
        project_id: ProjectId,
        filters: FilterParams,
        update_params: TransactionEventUpdateParams,
    ) -> None:
        base_statement = update(TransactionEventModel).where(TransactionEventModel.project_id == project_id)

        async with Atomic() as session:
            filter_set = FilterSet(
                session=session, model=TransactionEventModel, params=filters, base_statement=base_statement
            )
            await filter_set.update_by_filters(update_params)
```

Call site — fill only email-less rows of one external id:

```python
await self.transaction_event_app.update_by_filters(
    project_id,
    filters=TransactionEventUpdateFilterParams(
        external_profile_id=external_profile_id, source=source, email__isnull=True
    ),
    update_params=TransactionEventUpdateParams(email=email),
)
```

If the model uses `UpdatedDateMixin`, `update_by_filters` sets `updated_at` itself —
repositories do not add it manually (an explicitly passed value wins).

### extra_columns

For filtering on a computed field rather than a model column:

```python
state_expr = case(
    (CampaignModel.is_deleted.is_(True), literal(CampaignStateEnum.ARCHIVED)),
    (active_var.c.campaign_id.is_not(None), literal(CampaignStateEnum.LIVE)),
    else_=literal(CampaignStateEnum.DRAFT),
)

statement = select(CampaignModel, state_expr.label('state'))
filter_set = FilterSet(
    session=session,
    model=CampaignModel,
    params=params,
    base_statement=statement,
    extra_columns={'state': state_expr},
)
```
