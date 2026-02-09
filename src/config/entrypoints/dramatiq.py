from logging.config import dictConfig

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AgeLimit, AsyncIO, Callbacks, Pipelines, Retries, TimeLimit
from dramatiq.middleware.prometheus import Prometheus
from dramatiq.results import Results
from dramatiq.results.backends.redis import RedisBackend

from config.logging.config import LOG_CONFIG
from config.logging.sentry import configure_sentry
from config.settings import settings

from share.dramatiq.facade import BaseDramatiqFacade
from share.dramatiq.middlewares import TaskLoggingMiddleware

if not settings.DEBUG:
    dictConfig(LOG_CONFIG)

result_backend = RedisBackend(url=str(settings.DRAMATIQ_RESULT_BACKEND_REDIS_URL))
result_middleware = Results(
    backend=result_backend,
    result_ttl=10 * 60 * 1000,  # 10 minutes in ms
)

broker = RedisBroker(
    url=str(settings.DRAMATIQ_BROKER_REDIS_URL),
    health_check_interval=30,
    dead_message_ttl=24 * 60 * 60 * 1000,  # 24 hours in ms
    middleware=[
        AsyncIO(),
        AgeLimit(),
        TimeLimit(),
        Callbacks(),
        Retries(),
        Pipelines(),
        Prometheus(),
        TaskLoggingMiddleware(),
        result_middleware,
    ],
)

dramatiq.set_broker(broker)


class DramatiqFacade(BaseDramatiqFacade):
    base_dir = settings.ROOT_DIR
    module_pattern = 'app.*.infrastructure.ports.tasks'


dramatiq_facade_impl = DramatiqFacade()
dramatiq_facade_impl.setup_tasks()

configure_sentry()
