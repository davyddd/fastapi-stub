from redis.asyncio import Redis

from config.settings import settings

redis_client: Redis = Redis.from_url(str(settings.CACHE_REDIS_URL), decode_responses=True)
