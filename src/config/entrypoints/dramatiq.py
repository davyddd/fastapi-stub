import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AgeLimit, AsyncIO, Callbacks, CurrentMessage, Pipelines, Retries, TimeLimit
from dramatiq.results import Results
from dramatiq.results.backends.redis import RedisBackend

from config.databases.redis import redis_dramatiq_broker_client, redis_dramatiq_result_client
from config.databases.services.db_connections_closer import close_db_connections
from config.logging.configure import configure_logging_handlers
from config.logging.log_properties import log_properties_registry
from config.settings import settings

from share.dramatiq.actor_middlewares import (
    CloseDBConnectionsMiddleware,
    LogPropertiesManagerMiddleware,
    SentryTagsMiddleware,
    TaskLoggingMiddleware,
)
from share.dramatiq.facade import BaseDramatiqFacade
from share.dramatiq.middleware.health_check import HealthCheck
from share.dramatiq.middleware.prometheus import PrometheusMetrics

result_backend = RedisBackend(client=redis_dramatiq_result_client)
result_middleware = Results(
    backend=result_backend,
    result_ttl=10 * 60 * 1000,  # 10 minutes in ms
)

broker = RedisBroker(
    client=redis_dramatiq_broker_client,
    dead_message_ttl=24 * 60 * 60 * 1000,  # 24 hours in ms
    middleware=[
        AsyncIO(),
        AgeLimit(),
        TimeLimit(),
        Callbacks(),
        Retries(),
        CurrentMessage(),
        Pipelines(),
        PrometheusMetrics(),
        HealthCheck(),
        result_middleware,
    ],
)

dramatiq.set_broker(broker)


class DramatiqFacade(BaseDramatiqFacade):
    base_dir = settings.ROOT_DIR
    module_pattern = 'app.*.infrastructure.ports.tasks'
    actor_middlewares = (
        LogPropertiesManagerMiddleware(log_properties_registry),
        SentryTagsMiddleware(log_properties_registry),
        TaskLoggingMiddleware(),
        CloseDBConnectionsMiddleware(close_db_connections),
    )


dramatiq_facade_impl = DramatiqFacade()
dramatiq_facade_impl.setup_tasks()

configure_logging_handlers()
