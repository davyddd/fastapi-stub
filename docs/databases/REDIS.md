## Redis

Async Redis client based on `redis-py`. Used for caching and distributed locking.

### Cache

Base class for caching domain objects with JSON serialization.

**Example:**
```python
from typing import ClassVar

from redis.asyncio import Redis

from dddesign.structure.infrastructure.repositories import Repository

from config.databases.redis import redis_client
from config.databases.postgres import Atomic
from share.redis.cache import GenericCache

from app.profile_context.domains.entities.profile import Profile


class ProfileCache(GenericCache[Profile]):
    ttl = 10 * 60  # 10 minutes
    redis_client: ClassVar[Redis] = redis_client


profile_cache_impl = ProfileCache()


class ProfileRepository(Repository):
    cache: ProfileCache = profile_cache_impl

    async def get(self, profile_id: ProfileId) -> Profile | None:
        # Check cache first
        profile = await self.cache.get(profile_id)
        if profile:
            return profile

        # Fallback to database
        async with Atomic() as session:
            instance = await session.get(ProfileModel, profile_id)
            profile = instance.to_entity() if instance else None

        # Populate cache
        if profile:
            await self.cache.create(profile_id, profile)

        return profile


profile_repository_impl = ProfileRepository()
```

### Lock

Distributed lock for preventing concurrent access.

**Example:**
```python
from config.databases.redis import redis_client
from share.contextlib import async_suppress
from share.redis.lock import RedisLock, AlreadyAcquiredError


async with (
    async_suppress(AlreadyAcquiredError),
    RedisLock(redis_client, "some_key", timeout=30)
):
    await do_something()
```
