## Aerospike

Key-value records in sets of a namespace, through [ddaerospike](https://github.com/davyddd/ddaerospike) on
`aerospike-native`. Used for data that is read by key at high rate and may expire: feature flags, offloaded
payloads, counters.

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

A set is described by an `AerospikeData` model: every field is a bin, datetimes are `AerospikeTimestamp`, a nested
model is a composite bin. The model maps to and from the domain entity.

```python
from ddaerospike.data import AerospikeData, AerospikeTimestamp

from app.profile_context.domains.entities.profile import Profile


class ProfileData(AerospikeData[Profile]):
    name: str
    created_at: AerospikeTimestamp

    def to_entity(self, **kwargs) -> Profile:
        return Profile(name=self.name, created_at=self.created_at)

    @classmethod
    def from_entity(cls, entity: Profile) -> 'ProfileData':
        return cls(name=entity.name, created_at=entity.created_at)
```

### Manager

An `AerospikeManager[Data]` is the access to one set, a Django-style manager owned by a repository (it is not a
`dddesign` Repository itself). It is wired with the client factory, the namespace and the set.

```python
from ddaerospike.manager import AerospikeManager

from config.databases.aerospike import AerospikeConnectionAlias, aerospike_client_factory


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

`get_list` / `find_one` take an `AerospikeFilterCollection(ProfileData)`: one secondary-index filter and any number
of filter expressions, checked against the model's bins. A query with `use_index=True` needs a secondary index on
that bin, created on the cluster (`asinfo sindex-create`), not by code. See the ddaerospike README for the details.

`ttl_seconds` on the manager is set by every `put`, so the TTL slides: an active record keeps living, one nobody
touches expires. A `ttl` argument overrides it for that write. Without either a write leaves the record's TTL as
it is and a new record gets the namespace `default-ttl`, 0 locally: it never expires.

### Local setup

`docker-compose` runs a single-node Aerospike 8 with the `application_db` namespace (`aerospike/aerospike.conf`:
`default-ttl 0`, nsup on so writes may set a TTL, data in a file inside the `as-data` volume);
`AEROSPIKE_URL=aerospike://aerospike:3000/application_db` in `.env`. Sets are created on the first write. `asinfo`
and `aql` are available in the container:

```
docker compose exec aerospike asinfo -v "namespace/application_db"
docker compose exec aerospike aql -c "select * from application_db.feature_flag"
```
