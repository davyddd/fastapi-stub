from functools import partial

from redis import Redis as RedisSync
from redis.asyncio import Redis as RedisAsync
from redis.exceptions import ConnectionError, TimeoutError  # noqa: A004

from dddesign.structure.domains.constants import BaseEnum
from ddutils.connections import ConnectionManager, ConnectionManagerFactory
from ddutils.scoped_registry import ScopedRegistry, process_loop_scope

from config.settings import settings

config = {
    'max_connections': 20,
    'socket_connect_timeout': 5,
    'socket_timeout': 1,
    'retry_on_error': [ConnectionError, TimeoutError],
}


# Sync clients handed to the dramatiq broker and result backend at import time; dramatiq owns their lifetime
redis_dramatiq_broker_client: RedisSync = RedisSync.from_url(str(settings.DRAMATIQ_BROKER_REDIS_URL), **config)

redis_dramatiq_result_client: RedisSync = RedisSync.from_url(str(settings.DRAMATIQ_RESULT_BACKEND_REDIS_URL), **config)


class RedisConnectionAlias(str, BaseEnum):
    """Redis to talk to from async code, chosen per cache / lock like Postgres' `postgres_session_factory(alias=...)`."""

    CACHE = 'cache'

    @property
    def url(self) -> str:
        urls = {
            RedisConnectionAlias.CACHE: settings.CACHE_REDIS_URL,
        }
        return str(urls[self])


def _create_client(alias: RedisConnectionAlias) -> RedisAsync:
    return RedisAsync.from_url(alias.url, decode_responses=True, **config)  # type: ignore[invalid-argument-type]


def _build_client_registry(alias: RedisConnectionAlias) -> ScopedRegistry[RedisAsync]:
    # One async client per process and loop: `redis.asyncio` connections bind to the loop they were opened in.
    # The client is itself a pool (`max_connections`) and lives until `redis_client_factory.close()` on shutdown.
    return ScopedRegistry[RedisAsync](
        create_func=partial(_create_client, alias), scope_func=process_loop_scope, destructor_method_name='aclose'
    )


redis_client_registries: dict[RedisConnectionAlias, ScopedRegistry[RedisAsync]] = {
    alias: _build_client_registry(alias) for alias in RedisConnectionAlias
}

# `async with redis_client_factory() as client`, or `(alias=RedisConnectionAlias.CACHE)` to pick the Redis;
# the default `ConnectionManager` hands out the process-wide client and closes nothing on exit.
# `redis_client_factory.close()` on shutdown closes the clients of the current loop.
redis_client_factory: ConnectionManagerFactory[RedisConnectionAlias, RedisAsync, ConnectionManager[RedisAsync]] = (
    ConnectionManagerFactory(
        redis_client_registries,
        default=RedisConnectionAlias.CACHE,
        connection_manager_class=ConnectionManager[RedisAsync],
    )
)
