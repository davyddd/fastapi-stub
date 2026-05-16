from redis import Redis as RedisSync
from redis.asyncio import Redis as RedisAsync
from redis.exceptions import ConnectionError, TimeoutError  # noqa: A004

from config.settings import settings

config = {
    'max_connections': 20,
    'socket_connect_timeout': 5,
    'socket_timeout': 1,
    'retry_on_error': [ConnectionError, TimeoutError],
}

redis_dramatiq_broker_client: RedisSync = RedisSync.from_url(str(settings.DRAMATIQ_BROKER_REDIS_URL), **config)

redis_dramatiq_result_client: RedisSync = RedisSync.from_url(str(settings.DRAMATIQ_RESULT_BACKEND_REDIS_URL), **config)

redis_client: RedisAsync = RedisAsync.from_url(
    str(settings.CACHE_REDIS_URL),
    decode_responses=True,
    **config,  # type: ignore[invalid-argument-type]
)
