from dddesign.structure.domains.constants import BaseEnum

from config.settings import settings

from share.kafka.producer import BaseKafkaProducerRepository
from share.kafka.settings import ProducerConfig

BOOTSTRAP_SERVERS: list[str] = settings.KAFKA_BOOTSTRAP_SERVERS


class KafkaTopicName(str, BaseEnum):
    ...


class KafkaProducerRepository(BaseKafkaProducerRepository):
    bootstrap_servers = BOOTSTRAP_SERVERS
    config = ProducerConfig()


kafka_producer_repository_impl = KafkaProducerRepository()
