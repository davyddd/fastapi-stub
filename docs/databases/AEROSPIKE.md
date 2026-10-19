## Aerospike

Key-value records in sets of a namespace, through [ddaerospike](https://github.com/davyddd/ddaerospike) on
`aerospike-native`. Used for data that is read by key at high rate and may expire: feature flags, offloaded
payloads.

### Client

`aerospike-native`, the official Rust-core asyncio client, pinned exactly: it follows SemVer, but its API is
documented only through its type stubs. Two properties shape how it is wired:

- A client completes its futures on the event loop it was created in and cannot be reused from another loop,
  hence the `(pid, running loop)` scope of its registry.
- On import it installs uvloop as the global event loop policy, so every loop created afterwards is a uvloop one:
  uvicorn picks uvloop itself, dramatiq workers and scripts get it from this import. `AEROSPIKE_NO_UVLOOP=1` in the
  environment opts out.

Errors come out as the client raises them. Mind the hierarchy: `RecordNotFound`, `RecordExistsError`, timeouts
and the other mapped errors subclass `aerospike_native.exceptions.AerospikeError`, while a server code without a
mapping arrives as `aerospike_native.ServerError`, which does not; "any Aerospike error" is
`except (AerospikeError, ServerError)`.

`config.databases.aerospike` follows the Postgres / ClickHouse layout: `AerospikeConnectionAlias` names the cluster
(`url` is the `AerospikeDsn` from settings, `namespace` comes from it), `aerospike_client_registries` holds one
client per alias, process and event loop, and `aerospike_client_factory()` hands the client out. The clients are
closed on shutdown by `aerospike_client_factory.close()` from the FastAPI `lifespan` and the dramatiq `AsyncShutdown`
middleware.

### Records

A set is described by an `AerospikeData` model (`ddaerospike.data`): every field is a bin, and the model maps to
and from the domain entity. Bin names are at most 15 characters. Scalars and plain containers (`list[str]`,
`dict[str, int]`) are simple bins, written as they are. A `BaseModel` field is a composite bin: stored as a map,
written without its `None` values and validated on read; a list or dict with a schema is declared through a
pydantic `RootModel` (`class Tags(RootModel[list[str]])`). A field set to `None`, simple or composite, removes the
bin on `put`; to leave a bin untouched instead, drop it in `filter_bins`. An empty map or list is read back as is,
so a composite field that may be missing needs a default. Composite bins and plain containers are not filterable
beyond the null checks (see Filters).

A datetime bin is declared as `AerospikeTimestamp`: stored as integer microseconds since the epoch (UTC), read
back as an aware datetime, and the representation a filter compares a `datetime` / `date` value against. A bare
`datetime` / `date` field is rejected at class creation, but only on the model itself: use `AerospikeTimestamp`
inside composite models too, a bare `datetime` there is stored as an ISO string that no filter matches.

```python
from typing import Self

from ddaerospike.data import AerospikeData, AerospikeTimestamp

from app.profile_context.domains.entities.profile import Profile


class ProfileData(AerospikeData[Profile]):
    name: str
    created_at: AerospikeTimestamp

    def to_entity(self, **kwargs) -> Profile:
        return Profile(name=self.name, created_at=self.created_at)

    @classmethod
    def from_entity(cls, entity: Profile) -> Self:
        return cls(name=entity.name, created_at=entity.created_at)
```

### Manager

An `AerospikeManager[Data]` is the access to one set, a Django-style manager owned by a repository (it is not a
`dddesign` Repository itself). It is wired with the client factory, the namespace and the set.

```python
from typing import ClassVar

from ddaerospike.manager import AerospikeManager
from dddesign.structure.infrastructure.repositories import Repository

from config.databases.aerospike import AerospikeConnectionAlias, aerospike_client_factory

from app.profile_context.domains.entities.profile import Profile, ProfileId


class ProfileManager(AerospikeManager[ProfileData]):
    client_factory = aerospike_client_factory
    namespace = AerospikeConnectionAlias.PRIMARY.namespace
    set_name = 'profile'
    ttl_seconds = 30 * 24 * 60 * 60


class ProfileRepository(Repository):
    manager: ClassVar[ProfileManager] = ProfileManager()

    async def get(self, profile_id: ProfileId) -> Profile | None:
        data = await self.manager.get(profile_id)
        return data.to_entity() if data is not None else None

    async def save(self, profile: Profile) -> None:
        await self.manager.put(profile.id, ProfileData.from_entity(profile))
```

The manager's methods: `get(pk) -> Data | None`, `get_map(pks) -> dict[str, Data]` (keyed by `str(pk)`, a missing
or unanswered key is left out), `get_list(filters=None, limit=40)` and `find_one(filters)` returning
`AerospikeDataWithPK(pk, data)`, `put(pk, data, ttl=None, *, if_absent=False) -> bool` (merges the model's bins
into the record; `if_absent` is create-only, `False` when the record exists) and `delete(pk) -> bool`. `limit` is
an upper bound the server splits across its nodes: a query may return fewer records than `limit` although more
match, and there is no order. The `*_policy_fields` class attributes override the client policies; an override
replaces the whole dict, so extend `DEFAULT_WRITE_POLICY` and the others rather than start from scratch, or
`send_key=True` is gone and queries stop returning `pk`.

### Filters

`get_list` / `find_one` take an `AerospikeFilterCollection(ProfileData)` (`ddaerospike.filters`): the conditions
of one query on a set, ANDed, bound to the set's record model. `add_filter` checks that the bin exists and that the
value matches the scalar the bin holds, and a manager refuses a collection built for another model. The binding
matters because the server compares typed values: a value of another type than the bin matches nothing, silently.
The scalar of a bin follows its annotation: `bool`; `int` for `int`, `AerospikeTimestamp` (the value is a
`datetime` / `date`) and an `Enum` of ints; `float` for `float` and `Decimal`; `str` for `str`, `UUID` and an `Enum`
of strings. An `int` value widens to a `float` bin, any other mismatch raises. A list, a dict, a union of several
types and a composite bin take only the null checks.

| Operator | `int`, `float` bins | `str`, `bool` bins | with `use_index=True` |
|---|---|---|---|
| `EQUAL`, `NOT_EQUAL` | ✓ | ✓ | `EQUAL` on `int`, `str` |
| `GT`, `GTE`, `LT`, `LTE` | ✓ | | |
| `BETWEEN` `(low, high)`, inclusive | ✓ | | `int` |
| `IS_NULL`, `IS_NOT_NULL` (no value) | any bin, composite too | | |

```python
from ddaerospike.filters import AerospikeFilterCollection, AerospikeFilterOperator

filters = (
    AerospikeFilterCollection(ProfileData)
    .add_filter('project_id', AerospikeFilterOperator.EQUAL, project_id, use_index=True)
    .add_filter('created_at', AerospikeFilterOperator.GTE, since)
)
profiles = await self.manager.get_list(filters, limit=100)
```

`IS_NULL` is "the bin is missing", since the manager writes `None` as no bin; `NOT_EQUAL` on a missing bin is
false, so "not equal or missing" is two conditions. One secondary-index filter per query; a query with
`use_index=True` needs a secondary index on that bin (`asinfo sindex-create`, created by DevOps on the cluster, not
by code). Without an index the same condition goes in as a filter expression and the query reads the whole set.
The ddaerospike README has the rest.

### TTL

`ttl_seconds` on the manager is set by every `put`, so the TTL slides: an active record keeps living, one nobody
touches expires. A `ttl` argument overrides it for that write. Without either a write leaves the record's TTL as
it is and a new record gets the namespace `default-ttl`, 0 locally: it never expires. A namespace with
`nsup-period 0` refuses a write that sets a TTL (`ServerError`, FORBIDDEN); the local config runs nsup.

### Local setup

`docker-compose` runs a single-node Aerospike 8 with the `application_db` namespace (`aerospike/aerospike.conf`:
`default-ttl 0`, nsup on so writes may set a TTL, data in a file inside the `as-data` volume);
`AEROSPIKE_URL=aerospike://aerospike:3000/application_db` in `.env`. Sets are created on the first write. `asinfo`
and `aql` are available in the container:

```
docker compose exec aerospike asinfo -v "namespace/application_db"
docker compose exec aerospike aql -c "select * from application_db.feature_flag"
```
