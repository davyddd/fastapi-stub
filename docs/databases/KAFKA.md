## Kafka

Async Kafka client based on `aiokafka`. Serialization via `msgpack`.

### Producer

Base class for producing messages to Kafka.
Can be shared across the entire project — pass topic and objects implementing `Producible` protocol.

**Example:**
```python
from ddkafka.producer import BaseKafkaProducer

from config.databases.kafka import kafka_producer_factory


class EventProducer(BaseKafkaProducer):
    producer_factory = kafka_producer_factory
    # alias = KafkaConnectionAlias.PRIMARY  # None picks the factory's default


event_producer_impl = EventProducer()
```

`config.databases.kafka` follows the Postgres / ClickHouse layout: `KafkaConnectionAlias` names the cluster,
`kafka_producer_registries` holds one started producer per alias, process and event loop, and a producer class
points to `kafka_producer_factory`, which opens the producer of its `alias` for every send. `create` / `bulk_create` return once the record is in the
producer's buffer; aiokafka sends it in batches, and the buffer only reaches Kafka while the process runs. The
producers are flushed and closed on shutdown by `kafka_producer_factory.close()`, called from the FastAPI `lifespan`
and from the dramatiq `AsyncShutdown` middleware placed after `AsyncIO()`, so it runs on the worker's event loop
before the loop is closed.

### Consumer

Base class for consuming messages from Kafka with batch processing.
Use context name as `group_id` (e.g., `analytics_context` for analytics processing).

**Example:**
```python
from ddkafka.consumer import BaseKafkaConsumer

from config.databases.kafka import KafkaConnectionAlias


class ProfileOpenAppEventConsumer(BaseKafkaConsumer[ProfileOpenAppEvent]):
    bootstrap_servers = KafkaConnectionAlias.PRIMARY.bootstrap_servers
    topic = 'profile_open_app_event_topic'
    group_id = 'analytics_context'
    batch_size = 100
```

### Consumer Maker

Context manager for consumer initialization. Use in the Application layer.
Distributed lock prevents duplicate processing across workers — if a lock is already acquired, the task exits immediately.

**Example:**
```python
from ddkafka.consumer_maker import KafkaConsumerMaker
from ddredis.lock import RedisLock

from config.databases.redis import redis_client_factory


async with KafkaConsumerMaker(
    consumer_class=ProfileOpenAppEventConsumer,
    partition=partition,
    lock_class=RedisLock,
    lock_kwargs={'client_factory': redis_client_factory, 'timeout': 300},
) as consumer_maker:
    async for batch in consumer_maker.get_batches():
        await do_something(batch)
```
