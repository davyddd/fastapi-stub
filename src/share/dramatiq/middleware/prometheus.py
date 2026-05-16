from __future__ import annotations

from dramatiq.common import current_millis
from dramatiq.middleware.prometheus import Prometheus

_QUEUE_TIME_BUCKETS = (100, 500, 1_000, 5_000, 10_000, 30_000, 60_000, 300_000, float('inf'))


class PrometheusMetrics(Prometheus):
    """Extends the built-in Dramatiq Prometheus middleware with additional metrics.

    Adds:
    - dramatiq_messages_enqueued_total: counter of messages enqueued (retries excluded).
    - dramatiq_message_queue_time_milliseconds: histogram of time from enqueue to
      processing start (retries and delayed messages excluded).
    """

    def after_process_boot(self, broker):
        super().after_process_boot(broker)

        import prometheus_client as prom

        registry = prom.CollectorRegistry()

        self.messages_enqueued = prom.Counter(
            'dramatiq_messages_enqueued_total',
            'Total number of messages enqueued, excluding retries.',
            ['queue_name', 'actor_name'],
            registry=registry,
        )
        self.queue_time = prom.Histogram(
            'dramatiq_message_queue_time_milliseconds',
            'Time between message enqueue and processing start in milliseconds, for first attempts only.',
            ['queue_name', 'actor_name'],
            buckets=_QUEUE_TIME_BUCKETS,
            registry=registry,
        )

    def after_enqueue(self, broker, message, delay):
        super().after_enqueue(broker, message, delay)

        counter = getattr(self, 'messages_enqueued', None)
        if counter is None:
            return
        if 'retries' in message.options:
            return
        counter.labels(queue_name=message.queue_name, actor_name=message.actor_name).inc()

    def before_process_message(self, broker, message):
        super().before_process_message(broker, message)

        histogram = getattr(self, 'queue_time', None)
        if histogram is None:
            return
        if 'retries' in message.options:
            return
        if 'eta' in message.options:
            return
        queue_time_ms = max(0, current_millis() - message.message_timestamp)
        histogram.labels(queue_name=message.queue_name, actor_name=message.actor_name).observe(queue_time_ms)
