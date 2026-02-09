import time
from abc import ABC
from collections.abc import AsyncIterator
from dataclasses import asdict
from logging import getLogger
from typing import ClassVar, Generic, Protocol, Self, TypeVar, get_args

import msgpack
from aiokafka import AIOKafkaConsumer, TopicPartition

from share.kafka.settings import ConsumerConfig

logger = getLogger(__name__)


class Deserializable(Protocol):
    @classmethod
    def model_validate(cls, data: dict) -> Self:
        ...


DomainT = TypeVar('DomainT', bound=Deserializable)


class BaseKafkaConsumerRepository(ABC, Generic[DomainT]):
    """
    Base async Kafka consumer repository.

    Class Attributes:
        bootstrap_servers: Kafka servers address
        topic: Topic name
        group_id: Consumer group ID
        batch_size: Max records per poll
        poll_timeout_ms: Timeout for poll operation in milliseconds
        min_batch_fill_ratio: Minimum batch fill ratio to continue (0.0-1.0)
        config: Consumer configuration
    """

    bootstrap_servers: ClassVar[list[str]]
    topic: ClassVar[str]
    group_id: ClassVar[str]
    batch_size: ClassVar[int] = 1_000
    poll_timeout_ms: ClassVar[int] = 10_000
    min_batch_fill_ratio: ClassVar[float] = 0.1
    config: ClassVar[ConsumerConfig] = ConsumerConfig()

    _domain_class: ClassVar[type[Deserializable]]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        domain_class = get_args(cls.__orig_bases__[0])[0]  # ty: ignore[unresolved-attribute]
        if domain_class is None or isinstance(domain_class, TypeVar):
            raise TypeError(
                f'{cls.__name__} must specify domain type: class {cls.__name__}(BaseKafkaConsumerRepository[YourDomain])'
            )
        cls._domain_class = domain_class

        bootstrap_servers = getattr(cls, 'bootstrap_servers', None)
        if not bootstrap_servers:
            raise ValueError('`bootstrap_servers` class attribute must be set')
        if not isinstance(bootstrap_servers, list):
            raise ValueError('`bootstrap_servers` class attribute must be a list[str]')

        topic = getattr(cls, 'topic', None)
        if not topic:
            raise ValueError('`topic` class attribute must be set')
        if not isinstance(topic, str):
            raise ValueError('`topic` class attribute must be a string')

        group_id = getattr(cls, 'group_id', None)
        if not group_id:
            raise ValueError('`group_id` class attribute must be set')
        if not isinstance(group_id, str):
            raise ValueError('`group_id` class attribute must be a string')

        batch_size = getattr(cls, 'batch_size', None)
        if not batch_size:
            raise ValueError('`batch_size` class attribute must be set')
        if not isinstance(batch_size, int):
            raise ValueError('`batch_size` class attribute must be an integer')

        poll_timeout_ms = getattr(cls, 'poll_timeout_ms', None)
        if poll_timeout_ms is None:
            raise ValueError('`poll_timeout_ms` class attribute must be set')
        if not isinstance(poll_timeout_ms, int):
            raise ValueError('`poll_timeout_ms` class attribute must be an integer')

        min_batch_fill_ratio = getattr(cls, 'min_batch_fill_ratio', None)
        if min_batch_fill_ratio is None:
            raise ValueError('`min_batch_fill_ratio` class attribute must be set')
        if not isinstance(min_batch_fill_ratio, float):
            raise ValueError('`min_batch_fill_ratio` class attribute must be a float')
        if not (0 <= min_batch_fill_ratio <= 1):
            raise ValueError('`min_batch_fill_ratio` class attribute must be between 0 and 1')

        config = getattr(cls, 'config', None)
        if config is None:
            raise ValueError('`config` class attribute must be set')
        if not isinstance(config, ConsumerConfig):
            raise ValueError('`config` class attribute must be a ConsumerConfig')

    def __init__(self, partition: int):
        self._partition = partition
        self._topic_partition = TopicPartition(self.topic, partition)
        self._processed_offsets: dict[TopicPartition, int] = {}
        self._create_consumer()

    def _create_consumer(self) -> None:
        logger.info(
            {
                'message': 'KAFKA_CONSUMER: Creating consumer',
                'topic': self.topic,
                'partition': self._partition,
                'group_id': self.group_id,
            }
        )

        self._consumer = AIOKafkaConsumer(
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda v: self._domain_class.model_validate(msgpack.loads(v)),
            **asdict(self.config),
        )
        self._consumer.assign([self._topic_partition])

    async def start(self) -> None:
        await self._consumer.start()

        logger.info(
            {'message': 'KAFKA_CONSUMER: Started', 'topic': self.topic, 'partition': self._partition, 'group_id': self.group_id}
        )

    async def stop(self) -> None:
        await self._consumer.stop()
        logger.info(
            {'message': 'KAFKA_CONSUMER: Stopped', 'topic': self.topic, 'partition': self._partition, 'group_id': self.group_id}
        )

    async def get_batches(self, timestamp_threshold_minutes: int | None = None) -> AsyncIterator[tuple[DomainT, ...]]:
        """
        Returns an async iterator over batches of domain entities.

        Args:
            timestamp_threshold_minutes: Only messages OLDER than this threshold (in minutes) are included.
                                         Defaults to None (no filtering).
        """
        offset_limit: int | None = None
        if timestamp_threshold_minutes is not None:
            threshold_ms = int(time.time() * 1000) - (timestamp_threshold_minutes * 60 * 1000)
            offsets_for_times = await self._consumer.offsets_for_times({self._topic_partition: threshold_ms})
            if self._topic_partition in offsets_for_times and offsets_for_times[self._topic_partition]:
                offset_limit = offsets_for_times[self._topic_partition].offset

        while True:
            records_by_partition = await self._consumer.getmany(
                self._topic_partition, timeout_ms=self.poll_timeout_ms, max_records=self.batch_size
            )
            records = records_by_partition.get(self._topic_partition, [])

            logger.info(
                {
                    'message': 'KAFKA_CONSUMER: Retrieved batch',
                    'topic': self.topic,
                    'partition': self._partition,
                    'records_count': len(records),
                }
            )

            if not records:
                break

            # Filter by offset if timestamp threshold is set
            if offset_limit is not None:
                filtered_records = [r for r in records if r.offset < offset_limit]
                last_record = filtered_records[-1] if filtered_records else None
            else:
                filtered_records = records
                last_record = records[-1]

            if not last_record:
                break

            # Check if we should break (batch too small)
            should_break = len(records) < self.batch_size * self.min_batch_fill_ratio

            yield tuple(record.value for record in filtered_records)

            # Track offset for commit
            self._processed_offsets[self._topic_partition] = last_record.offset + 1

            if should_break:
                break

    async def commit(self) -> None:
        if self._processed_offsets:
            await self._consumer.commit(self._processed_offsets)

        logger.info(
            {
                'message': 'KAFKA_CONSUMER: Committed offsets',
                'topic': self.topic,
                'partition': self._partition,
                'offsets': str(self._processed_offsets),
            }
        )

        self._processed_offsets.clear()
