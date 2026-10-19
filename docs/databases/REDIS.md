## Redis

Async Redis client based on `redis-py`, through [ddredis](https://github.com/davyddd/ddredis): the cache, the
distributed lock and `RedisFeatureFlagStorage`, the alternative to the Aerospike feature flag storage in use.

`config.databases.redis` follows the Postgres / ClickHouse layout: `RedisConnectionAlias` names the Redis to talk
to, `redis_client_registries` holds one client per alias, process and event loop (`redis.asyncio` connections bind
to the loop they were opened in), and `redis_client_factory()` hands the client out; a cache class points to the
factory and opens the client of its `alias` for every call. The clients are created with `decode_responses=True`,
pooled (`max_connections=20`) and retry connection and timeout errors (redis-py's default `Retry`, 3 attempts with
backoff). They are closed on shutdown by `redis_client_factory.close()` from the FastAPI `lifespan` and the dramatiq
`AsyncShutdown` middleware. The module also builds the two sync clients the dramatiq broker and result backend take
at import time; dramatiq owns their lifetime.

### Cache

`GenericCache[Domain]` caches domain objects as JSON under `:<snake_case_domain>:<key>` with the class `ttl` (±10%
jitter). It is best effort: every `RedisError` reads as a miss and writes are dropped silently, so a `None` from
the cache never means "the object does not exist", and the cache is not for state where `None` has a meaning of
its own. `update` is `create`; `get_list` / `delete_by_filters` scan the keyspace with `SCAN MATCH`, so they are
for small sets of keys, not for hot paths.

**Example:**
```python
from dddesign.structure.infrastructure.repositories import Repository
from ddredis.cache import GenericCache

from config.databases.postgres import postgres_session_factory
from config.databases.redis import redis_client_factory

from app.profile_context.domains.entities.profile import Profile


class ProfileCache(GenericCache[Profile]):
    ttl = 10 * 60  # 10 minutes
    client_factory = redis_client_factory
    # alias = RedisConnectionAlias.CACHE  # None picks the factory's default


profile_cache_impl = ProfileCache()


class ProfileRepository(Repository):
    cache: ProfileCache = profile_cache_impl

    async def get(self, profile_id: ProfileId) -> Profile | None:
        # Check cache first
        profile = await self.cache.get(profile_id)
        if profile:
            return profile

        # Fallback to database
        async with postgres_session_factory() as session:
            instance = await session.get(ProfileModel, profile_id)
            profile = instance.to_entity() if instance else None

        # Populate cache
        if profile:
            await self.cache.create(profile_id, profile)

        return profile


profile_repository_impl = ProfileRepository()
```

### Lock

`RedisLock(client_factory, key, timeout=10.0, blocking=False, *, alias=None)`: a distributed lock for preventing
concurrent access. The client comes from `redis_client_factory` like the cache's (`alias=` is keyword-only and
picks the Redis), borrowed for every `acquire` / `release` / `extend`; the lock object holds only its token. A held
lock raises `AlreadyAcquiredError` from `acquire`, also after the wait of `blocking=True` runs out.

**Example:**
```python
from ddredis.lock import AlreadyAcquiredError, RedisLock
from ddutils.context_helpers import async_suppress

from config.databases.redis import redis_client_factory


async with async_suppress(AlreadyAcquiredError), RedisLock(redis_client_factory, 'some_key', timeout=30):
    await do_something()
```

`timeout` is the TTL of the key in Redis, not a cancellation of the block: when the block outlives it another
worker enters while the first is still running. Pick a timeout above the worst-case runtime, or call `extend()`
as a heartbeat; it sets the TTL to the full `timeout` from now rather than adding to it. `release()` tolerates a
key that already expired.
