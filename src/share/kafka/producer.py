from abc import ABC
from dataclasses import asdict
from typing import ClassVar, Protocol

import msgpack
from aiokafka import AIOKafkaProducer

from share.kafka.settings import ProducerConfig


class Producible(Protocol):
    @property
    def idempotent_key(self) -> str | None:
        ...

    def model_dump(self, *args, **kwargs) -> dict:
        ...


class BaseKafkaProducerRepository(ABC):
    """
    Base async Kafka producer.

    Class Attributes:
        bootstrap_servers: Kafka servers address
        config: Producer configuration

    Example:
        from config.databases.kafka import bootstrap_servers

        class EventProducerRepository(BaseKafkaProducerRepository):
            bootstrap_servers = bootstrap_servers
            config = ProducerConfig(acks=1, linger_ms=100)

        producer_repository_impl = EventProducerRepository()
        await producer_repo_impl.bulk_create('topic', events)
    """

    bootstrap_servers: ClassVar[list[str]]
    config: ClassVar[ProducerConfig] = ProducerConfig()

    _producer: ClassVar[AIOKafkaProducer | None] = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        bootstrap_servers = getattr(cls, 'bootstrap_servers', None)
        if not bootstrap_servers:
            raise ValueError('`bootstrap_servers` class attribute must be set')
        if not isinstance(bootstrap_servers, list):
            raise ValueError('`bootstrap_servers` class attribute must be a list[str]')

        config = getattr(cls, 'config', None)
        if config is None:
            raise ValueError('`config` class attribute must be set')
        if not isinstance(config, ProducerConfig):
            raise ValueError('`config` class attribute must be a ProducerConfig')

    @classmethod
    async def _get_producer(cls) -> AIOKafkaProducer:
        if cls._producer is None:
            cls._producer = AIOKafkaProducer(
                bootstrap_servers=cls.bootstrap_servers,
                value_serializer=lambda v: msgpack.dumps(v.model_dump(mode='json')),
                key_serializer=lambda v: str(v).encode('utf-8'),
                **asdict(cls.config),
            )
            await cls._producer.start()

        return cls._producer

    async def create(self, topic: str, event: Producible):
        producer = await self._get_producer()
        await producer.send(topic, key=event.idempotent_key, value=event)

    async def bulk_create(self, topic: str, events: list[Producible]):
        producer = await self._get_producer()
        for event in events:
            await producer.send(topic, key=event.idempotent_key, value=event)
