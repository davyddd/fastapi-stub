## Kafka

Async Kafka client based on `aiokafka`. Serialization via `msgpack`.

### Producer

Base class for producing messages to Kafka.
Can be shared across the entire project — pass topic and objects implementing `Producible` protocol.

**Example:**
```python
from pydantic import BaseModel

from dddesign.structure.infrastructure.repositories import Repository

from config.databases.kafka import BOOTSTRAP_SERVERS
from share.kafka.producer import BaseKafkaProducerRepository


class EventProducerRepository(BaseKafkaProducerRepository):
    bootstrap_servers = BOOTSTRAP_SERVERS


event_producer_repository_impl = EventProducerRepository()
```

### Consumer

Base class for consuming messages from Kafka with batch processing.
Use context name as `group_id` (e.g., `analytics_context` for analytics processing).

**Example:**
```python
from pydantic import BaseModel

from dddesign.structure.infrastructure.repositories import Repository

from config.databases.kafka import BOOTSTRAP_SERVERS
from share.kafka.consumer import BaseKafkaConsumerRepository


class ProfileOpenAppEventConsumerRepository(BaseKafkaConsumerRepository[ProfileOpenAppEvent]):
    bootstrap_servers = BOOTSTRAP_SERVERS
    topic = 'profile_open_app_event_topic'
    group_id = 'analytics_context'
    batch_size = 100
```

### Consumer Maker

Context manager for consumer initialization. Use in the Application layer.
Distributed lock prevents duplicate processing across workers — if a lock is already acquired, the task exits immediately.

**Example:**
```python
from share.kafka.consumer_maker import KafkaConsumerRepositoryMaker
from share.redis.lock import RedisLock

from config.databases.redis import redis_client


async with KafkaConsumerRepositoryMaker(
    consumer_class=ProfileOpenAppEventConsumerRepository,
    partition=partition,
    lock_class=RedisLock,
    lock_kwargs={'redis_client': redis_client, 'timeout': 300}
) as consumer_maker:
    async for batch in consumer_maker.get_batches():
        await do_something(batch)
```
