## Kafka

Event streaming through [ddkafka](https://github.com/davyddd/ddkafka) on `aiokafka`, payloads serialized with
`msgpack`. `config.databases.kafka` follows the Postgres / ClickHouse layout: `KafkaConnectionAlias` names the
cluster (`bootstrap_servers` comes from the `KafkaDsn` in settings), `kafka_producer_registries` holds one started
producer per alias, process and event loop, `kafka_producer_factory()` hands it out, and `kafka_producer_impl` is
the producer the application sends with. Consumers take the cluster from the same alias.

### Topics

Topics are declared once in `KafkaTopicName` of `config.databases.kafka`, with their partition count: the producer
sends to `KafkaTopicName.X`, the consumer tasks iterate `KafkaTopicName.X.partitions`. The partition count is the
topic's, set when the topic is created on the cluster, so one place in the code has to know it:

```python
class KafkaTopicName(str, BaseEnum):
    PROFILE_EVENT = 'profile_event'

    @property
    def partitions(self) -> int:
        return {KafkaTopicName.PROFILE_EVENT: 4}[self]
```

### Producer

`kafka_producer_impl` from `config.databases.kafka` is the one producer of the application: repositories and
adapters import it and call `create(topic, event)` or `bulk_create(topic, events)`, no subclass per context. An
event is anything with `model_dump` and an `idempotent_key` property (the `Producible` protocol); the key becomes
the record key, so records with the same key land on the same partition, and `None` sends no key.

```python
from dddesign.structure.infrastructure.repositories import Repository

from config.databases.kafka import KafkaTopicName, kafka_producer_impl
from app.profile_context.domains.dto.profile_event import ProfileEvent


class ProfileEventRepository(Repository):
    async def create(self, event: ProfileEvent) -> None:
        await kafka_producer_impl.create(KafkaTopicName.PROFILE_EVENT, event)
```

`create` / `bulk_create` return once the record is in the producer's buffer; aiokafka sends it in batches
(`linger_ms=50`), and the buffer only reaches Kafka while the process runs. The producers are flushed and closed on
shutdown by `kafka_producer_factory.close()`, called from the FastAPI `lifespan` and from the dramatiq
`AsyncShutdown` middleware placed after `AsyncIO()`, so it runs on the worker's event loop before the loop is
closed; a process killed without it loses up to `linger_ms` worth of records.

A record the broker rejects does not fail `create`: the rejection arrives later and is only visible as the
`KAFKA_PRODUCER: Delivery failed` ERROR log entry. The default `ProducerConfig(acks='all')` waits for every in-sync
replica, which is where that happens: a topic with fewer replicas than the cluster's `min.insync.replicas` rejects
every record with `NotEnoughReplicas`. The single-broker compose works because its `min.insync.replicas` is 1; on a
cluster whose topics are not yet created with enough replicas, pass `ProducerConfig(acks=1)` in
`_build_producer_registry` until they are, and say so in a comment. `enable_idempotence` is off on purpose:
consumers are at-least-once and dedupe by `idempotent_key` anyway.

### Consumer

`BaseKafkaConsumer[Event]` reads one partition in batches: one instance is assigned one partition (`assign`, not
`subscribe`), so it never joins the consumer group and the group only stores its offsets. Use the context name as
`group_id`.

```python
from ddkafka.consumer import BaseKafkaConsumer

from config.databases.kafka import KafkaConnectionAlias, KafkaTopicName
from app.analytics_context.domains.dto.profile_event import ProfileEvent


class ProfileEventConsumer(BaseKafkaConsumer[ProfileEvent]):
    bootstrap_servers = KafkaConnectionAlias.PRIMARY.bootstrap_servers
    topic = KafkaTopicName.PROFILE_EVENT
    group_id = 'analytics_context'
    batch_size = 100
```

The offsets of a batch are recorded before it is handed out, so `commit()` right after processing it acknowledges
that batch; a `commit()` before the processing means a failure in the middle loses the records. A record that
cannot be deserialized raises `MessageDeserializationError` with its offset and the partition stays there until the
offset is moved; `skip_undeserializable = True` logs and drops such records instead, and the next commit moves past
them for good. `get_batches(timestamp_threshold_minutes=5)` reads only records older than five minutes, for a
consumer that deliberately lags. `enable_auto_commit` accepts only `False`. The defaults and the rest of the knobs
are in the ddkafka README.

### Consumer Maker

`KafkaConsumerMaker` wraps a consumer in a `RedisLock`, so one partition is processed by one worker at a time
across the deployment. It is used from the Application layer, in an application dedicated to the consumption
(see [IMPORTS.md](../conventions/IMPORTS.md)), and started by a periodic task per partition:

```python
from datetime import timedelta

from ddkafka.consumer_maker import KafkaConsumerMaker
from ddredis.lock import AlreadyAcquiredError, RedisLock
from ddutils.context_helpers import async_suppress

from config.databases.redis import redis_client_factory


class ProfileEventConsumerApp(Application):
    async def consume(self, partition: int) -> None:
        # another worker holds the partition: `acquire` raises, nothing to do this tick
        async with (
            async_suppress(AlreadyAcquiredError),
            KafkaConsumerMaker(
                consumer_class=ProfileEventConsumer,
                partition=partition,
                lock_class=RedisLock,
                lock_kwargs={'client_factory': redis_client_factory, 'timeout': 300},
            ) as maker,
        ):
            async for batch in maker.get_batches():
                await self._process(batch)


# ports/tasks: one periodic task fans out over the partitions
@cron('* * * * *')
@dramatiq.actor(queue_name='analytics_context')
async def profile_event_consumer_app_consume_periodic_task():
    for partition in range(KafkaTopicName.PROFILE_EVENT.partitions):
        dramatiq_facade_impl.send_task('profile_event_consumer_app_consume_task', partition=partition)
```

The lock key is `'{group_id}_{topic}_partition_{partition}'`, so `lock_kwargs` must not contain `key`. Every
batch is committed as a whole after the loop body is done with it; an exit caused by an exception does not commit,
the batch is read again next time, so processing must tolerate repeated records (`idempotent_key`). Call
`maker.checkpoint()` yourself only once a batch is processed. A consumer that fails to start raises
`ConsumerStartError` after releasing the lock.

With `stream=True` the consumer stays on its partition when the topic runs dry and the cron becomes a supervisor:
every tick tries to start one, the lock turns all but the first away. The pace must fit the lock,
`stream_round_pause` plus the consumer's `poll_timeout_ms` may not exceed half of the lock timeout (`ValueError`
at construction), and that timeout is also the recovery time after a killed worker, so a streaming consumer wants
a lock of tens of seconds, not minutes.
