from dataclasses import dataclass


@dataclass(frozen=True)
class ProducerConfig:
    acks: int = 1
    linger_ms: int = 50
    max_batch_size: int = 32_000
    retry_backoff_ms: int = 500
    metadata_max_age_ms: int = 30_000
    request_timeout_ms: int = 5_000


@dataclass(frozen=True)
class ConsumerConfig:
    auto_offset_reset: str = 'earliest'
    enable_auto_commit: bool = False
    session_timeout_ms: int = 20_000
    request_timeout_ms: int = 25_000
    heartbeat_interval_ms: int = 6_500
    retry_backoff_ms: int = 1_000
    fetch_min_bytes: int = 120_000
    fetch_max_bytes: int = 125_000_000
    fetch_max_wait_ms: int = 1_000
    max_partition_fetch_bytes: int = 25_000_000
