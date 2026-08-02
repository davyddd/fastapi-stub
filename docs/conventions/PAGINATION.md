## Pagination

HTTP contract for list endpoints. The model's query capabilities live in its
`FilterParams` in the repository module ([FILTERING.md](./FILTERING.md)); the route wraps
that contract into a `QueryParams` — `filter[...]` aliases, `page`/`limit`, `search`,
`ordering` — and immediately projects it back via `params.filter_params`. `QueryParams`
never leaves the route: applications and repositories are typed with the model's
`FilterParams`.

### Components

| Component | Path | Purpose |
|---|---|---|
| `QueryParams` | `share.pagination.query_params` | HTTP query contract of a list endpoint, built from a `FilterParams` |
| `PaginatedResponse` | `share.pagination.response` | The single list response with the unified `Pagination` meta |
| `Pagination` | `share.pagination.response` | One shape for both styles: `page`/`limit` always, `count` optional, `next_cursor`/`prev_cursor` on keyset lists |

### Usage

#### 1. Build QueryParams in the route module

```python
from typing import Annotated

from fastapi import APIRouter, Query

from share.pagination import PaginatedResponse, QueryParams

from app.campaign_context.infrastructure.repositories.campaign import CampaignFilterParams

router = APIRouter()

CampaignQueryParams = QueryParams.build('CampaignQueryParams', CampaignFilterParams)


@router.get('/')
async def campaign_list(
    project_id: ProjectId,
    account: CurrentAccountDep,
    params: Annotated[CampaignQueryParams, Query()],
) -> PaginatedResponse[Campaign]:
    return await campaign_crud_app_impl.get_list(project_id, params.filter_params)
```

`QueryParams.build(name, filter_params)` derives everything from the contract: filter
fields become flat `filter[...]`-aliased query fields, `ordering` becomes an enum built
from `ordering_fields` (default `default_ordering`), `search` appears when
`search_fields` is declared.

**Built-in fields (always available):**
- `page` — page number (>= 1, default 1)
- `limit` — page size (1–100, default 20)
- `cursor` — opaque keyset cursor; page/limit endpoints just never receive it

`offset` is not an HTTP concern — it is a derived property on `FilterParams`.

**URL examples:**
```
GET /campaigns/?page=1&limit=20
GET /campaigns/?ordering=-created_at
GET /campaigns/?search=newsletter
GET /campaigns/?filter[state__in]=DRAFT&filter[state__in]=INACTIVE
GET /campaigns/?search=john&filter[state__in]=LIVE&ordering=created_at
```

#### 2. Application — typed with the model's contract

Applications receive the `FilterParams` directly (proper typing, no HTTP artifacts);
the response meta is derived from the same contract via `Pagination.from_params`:

```python
from share.pagination import PaginatedResponse, Pagination

from app.campaign_context.infrastructure.repositories.campaign import CampaignFilterParams


async def get_list(self, project_id: ProjectId, params: CampaignFilterParams) -> PaginatedResponse[Campaign]:
    count = await self.campaign_app.count(project_id, params)
    campaigns, next_cursor, prev_cursor = await self.campaign_app.get_list(project_id, params)
    return PaginatedResponse.factory(
        items=campaigns,
        pagination=Pagination.from_params(params, count=count, next_cursor=next_cursor, prev_cursor=prev_cursor),
    )
```

Keyset endpoints need no extra plumbing — `cursor` is a query field of `FilterParams`
and rides the same projection. They skip the expensive COUNT and fill the cursors
instead — a non-null `next_cursor` IS the "there is more" signal:

```python
return PaginatedResponse.factory(
    items=aggregates,
    pagination=Pagination.from_params(params, next_cursor=next_cursor, prev_cursor=prev_cursor),
)
```

The client always sends `page` and echoes `next_cursor`/`prev_cursor` when it has one:
with a cursor the server takes the fast keyset path; without one it falls back to
page/OFFSET (arbitrary page jumps, slower on deep pages).

Repositories accept the `FilterParams` contract and never see HTTP — see
[FILTERING.md](./FILTERING.md).

**Response format** (one shape; keyset lists fill the cursors and may skip `count`):
```json
{"data": [...], "meta": {"pagination": {"page": 1, "limit": 20, "count": 42, "next_cursor": null, "prev_cursor": null}}}
{"data": [...], "meta": {"pagination": {"page": 2, "limit": 50, "count": null, "next_cursor": "...", "prev_cursor": "..."}}}
```

### Checklist for adding a list endpoint

1. Declare the model's contract in the repository module
   ([FILTERING.md](./FILTERING.md)): filters declaration + `FilterParams.build()` with
   ordering/search config
2. In Repository — `get_list` / `count` accepting the `FilterParams`; `FilterSet.select()`
   returns the page objects plus both cursors, `count()` the number
3. In Application — accept the `<R>FilterParams`, build `PaginatedResponse.factory()`
   with `Pagination.from_params()`
4. In the route module — `QueryParams.build('<R>QueryParams', <R>FilterParams)`, bind with
   `Annotated[<R>QueryParams, Query()]`, call the application with `params.filter_params`
