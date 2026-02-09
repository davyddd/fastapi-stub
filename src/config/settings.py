import json
import os

from dotenv import load_dotenv
from pydantic import ClickHouseDsn, HttpUrl, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from dddesign.structure.domains.constants import BaseEnum

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

    CLICKHOUSE_URL: ClickHouseDsn

    DRAMATIQ_BROKER_REDIS_URL: RedisDsn
    DRAMATIQ_RESULT_BACKEND_REDIS_URL: RedisDsn
    CACHE_REDIS_URL: RedisDsn

    KAFKA_BOOTSTRAP_SERVERS: list[str]
    KAFKA_TOPIC_PARTITIONS_SES_EVENT: int
    KAFKA_TOPIC_PARTITIONS_PROFILE_EVENT: int

    SENTRY_DSN: HttpUrl | None = None

    @field_validator('KAFKA_BOOTSTRAP_SERVERS', mode='before')
    @classmethod
    def parse_kafka_bootstrap_servers(cls, v: str | list) -> list:
        if isinstance(v, list):
            return v
        return json.loads(v)


settings = Settings()  # type: ignore
