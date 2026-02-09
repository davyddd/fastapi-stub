from abc import ABC
from functools import cached_property
from random import randint
from typing import ClassVar, Generic, Protocol, Self, TypeVar, cast, get_args

from redis.asyncio import Redis

from ddutils.convertors import convert_camel_case_to_snake_case

from share.redis.decorators import suppress_redis_errors

JITTER_PERCENT = 10


class Serializable(Protocol):
    """Protocol for objects that can be serialized/deserialized to/from JSON."""

    @classmethod
    def model_validate_json(cls, json_data: str | bytes) -> Self:
        ...

    def model_dump_json(self) -> str:
        ...


class Stringable(Protocol):
    def __str__(self) -> str:
        ...


DomainT = TypeVar('DomainT', bound=Serializable)


class GenericCache(ABC, Generic[DomainT]):
    """
    GenericCache: An async generic caching repository for managing domain objects in Redis.

    This class provides a base implementation for caching domain objects in Redis.
    It supports CRUD operations (`get`, `create`, `update`, `delete`)
    and uses JSON serialization/deserialization to store and retrieve data.

    Domain class must implement `model_validate_json` and `model_dump_json` methods
    (compatible with Pydantic, msgspec, or custom implementations).

    Class Attributes:
        ttl (int): Time-to-live for cache entries in seconds. Default is 5 minutes.
        redis_client (Redis): Redis client instance.

    Example Usage:
        from config.databases.redis import redis_client

        class MyDomain(BaseModel):
            id: int
            name: str

        class MyDomainCache(GenericCache[MyDomain]):
            ttl = 10 * 60  # 10 minutes
            redis_client = redis_client

        cache = MyDomainCache()

        domain = MyDomain(id=1, name="Test")
        await cache.create(key=domain.id, value=domain)
        retrieved = await cache.get(key=1)
    """

    _domain_class: ClassVar[type[Serializable]]

    ttl: ClassVar[int] = 5 * 60  # 5 minutes
    redis_client: ClassVar[Redis]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        domain_class = get_args(cls.__orig_bases__[0])[0]  # ty: ignore[unresolved-attribute]
        if domain_class is None or isinstance(domain_class, TypeVar):
            raise TypeError(f'{cls.__name__} must specify domain type: class {cls.__name__}(GenericCache[YourDomain])')

        cls._domain_class = domain_class

    @cached_property
    def _key_prefix(self) -> str:
        return convert_camel_case_to_snake_case(self._domain_class.__name__)

    @cached_property
    def _jitter(self) -> int:
        return self.ttl * JITTER_PERCENT // 100

    def _generate_key(self, key: Stringable) -> str:
        """Generates a Redis key for the given identifier with the domain-specific prefix."""
        return f':{self._key_prefix}:{key!s}'

    def _generate_ttl(self) -> int:
        """Generates a TTL value with jitter."""
        return self.ttl + randint(-self._jitter, self._jitter)

    @suppress_redis_errors
    async def get(self, key: Stringable) -> DomainT | None:
        """Retrieves and deserializes a domain object from the cache by its key."""
        cached_data = await self.redis_client.get(self._generate_key(key))
        if not cached_data:
            return None

        try:
            return cast(DomainT, self._domain_class.model_validate_json(cached_data))
        except Exception:  # noqa: BLE001
            return None

    @suppress_redis_errors
    async def create(self, key: Stringable, value: DomainT) -> None:
        """Caches a new domain object or overwrites an existing one. Sets a TTL for the entry."""
        _key = self._generate_key(key)
        await self.redis_client.set(_key, value.model_dump_json(), ex=self._generate_ttl())

    @suppress_redis_errors
    async def update(self, key: Stringable, value: DomainT) -> None:
        """Updates a domain object in the cache. Alias for `create`."""
        await self.create(key=key, value=value)

    @suppress_redis_errors
    async def delete(self, key: Stringable) -> None:
        """Removes a domain object from the cache by its key."""
        await self.redis_client.delete(self._generate_key(key))
