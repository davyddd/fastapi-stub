import os

from dotenv import load_dotenv
from pydantic import ClickHouseDsn, HttpUrl, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

from ddaerospike.dsn import AerospikeDsn
from dddesign.structure.domains.constants import BaseEnum
from ddkafka.dsn import KafkaDsn

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
DOTENV_PATH = os.path.join(CONFIG_DIR, '.env')


# Load environment variables from .env into os.environ so they are accessible
# throughout the system via os.getenv(), even if not defined in the Settings class.
load_dotenv(DOTENV_PATH, override=False)


class Environment(str, BaseEnum):
    LOCAL = 'local'
    DEV = 'dev'
    PRODUCTION = 'production'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=DOTENV_PATH, extra='ignore')

    ROOT_DIR: str = os.path.dirname(CONFIG_DIR)

    DEBUG: bool = True
    PROJECT_NAME: str
    SERVER_URL: str
    ENVIRONMENT: Environment

    POSTGRES_URL: PostgresDsn
    # read replica; falls back to POSTGRES_URL when not set, so code using the replica works without one
    POSTGRES_REPLICA_URL: PostgresDsn | None = None

    CLICKHOUSE_URL: ClickHouseDsn

    DRAMATIQ_BROKER_REDIS_URL: RedisDsn
    DRAMATIQ_RESULT_BACKEND_REDIS_URL: RedisDsn
    CACHE_REDIS_URL: RedisDsn

    KAFKA_URL: KafkaDsn  # kafka://host[:port][,host[:port]]
    AEROSPIKE_URL: AerospikeDsn  # aerospike://host[:port][,host[:port]]/<namespace>

    SENTRY_DSN: HttpUrl | None = None


settings = Settings()  # type: ignore
