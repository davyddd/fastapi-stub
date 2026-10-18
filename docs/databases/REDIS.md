## Redis

Async Redis client based on `redis-py`. Used for caching and distributed locking.

`config.databases.redis` follows the Postgres / ClickHouse layout: `RedisConnectionAlias` names the Redis to talk
to, `redis_client_registries` holds one client per alias, process and event loop (`redis.asyncio` connections bind
to the loop they were opened in), and `redis_client_factory()` hands the client out; a cache class points to the factory and opens the client of
its `alias` for every call. The clients are closed on
shutdown by `redis_client_factory.close()` from the FastAPI `lifespan` and the dramatiq `AsyncShutdown` middleware.

### Cache

Base class for caching domain objects with JSON serialization.

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

Distributed lock for preventing concurrent access. The client comes from `redis_client_factory` like the cache's
(`alias=` picks the Redis); the lock borrows it for its lifetime.

**Example:**
```python
from ddredis.lock import AlreadyAcquiredError, RedisLock

from config.databases.redis import redis_client_factory
from ddutils.context_helpers import async_suppress


async with async_suppress(AlreadyAcquiredError), RedisLock(redis_client_factory, 'some_key', timeout=30):
    await do_something()
```
