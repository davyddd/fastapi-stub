from functools import partial

from aiokafka import AIOKafkaProducer

from dddesign.structure.domains.constants import BaseEnum
from ddkafka.config import ProducerConfig
from ddkafka.producer import BaseKafkaProducer, create_producer
from ddutils.connections import ConnectionManager, ConnectionManagerFactory
from ddutils.scoped_registry import ScopedRegistry

from config.databases.scopes import process_loop_scope
from config.settings import settings


class KafkaConnectionAlias(str, BaseEnum):
    """Cluster to produce to, chosen per producer repository like Postgres' `postgres_session_factory(alias=...)`."""

    PRIMARY = 'primary'

    @property
    def bootstrap_servers(self) -> list[str]:
        urls = {
            KafkaConnectionAlias.PRIMARY: settings.KAFKA_URL,
        }
        return urls[self].bootstrap_servers


class KafkaTopicName(str, BaseEnum): ...


def _build_producer_registry(alias: KafkaConnectionAlias) -> ScopedRegistry[AIOKafkaProducer]:
    # One producer per process and loop, started on the first send. It is itself a buffer plus a sender task,
    # so it has to be closed on shutdown (`kafka_producer_factory.close()`): `stop` sends what is still buffered.
    return ScopedRegistry[AIOKafkaProducer](
        create_func=partial(create_producer, alias.bootstrap_servers, ProducerConfig()),
        scope_func=process_loop_scope,
        destructor_method_name='stop',
    )


kafka_producer_registries: dict[KafkaConnectionAlias, ScopedRegistry[AIOKafkaProducer]] = {
    alias: _build_producer_registry(alias) for alias in KafkaConnectionAlias
}

# `async with kafka_producer_factory() as producer`, or `(alias=KafkaConnectionAlias.PRIMARY)` to pick the cluster;
# the default `ConnectionManager` hands out the process-wide producer and closes nothing on exit.
# `kafka_producer_factory.close()` on shutdown flushes and stops the producers of the current loop.
kafka_producer_factory: ConnectionManagerFactory[
    KafkaConnectionAlias, AIOKafkaProducer, ConnectionManager[AIOKafkaProducer]
] = ConnectionManagerFactory(
    kafka_producer_registries,
    default=KafkaConnectionAlias.PRIMARY,
    connection_manager_class=ConnectionManager[AIOKafkaProducer],
)


class KafkaProducer(BaseKafkaProducer):
    producer_factory = kafka_producer_factory  # `alias` stays None: the factory's default cluster


kafka_producer_impl = KafkaProducer()
