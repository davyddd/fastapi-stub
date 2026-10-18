from collections.abc import Awaitable, Callable

from dramatiq.asyncio import get_event_loop_thread
from dramatiq.middleware import Middleware


class AsyncShutdown(Middleware):
    """
    Runs coroutines on the worker's event loop when the worker shuts down, after the actors
    have finished: closing async clients that live in that loop (a Kafka producer that still
    holds a buffer, a connection pool).

    Place it after `AsyncIO()` in the broker's middleware list: dramatiq emits `after_worker_shutdown`
    in reverse order, so this hook runs while the loop thread `AsyncIO` manages is still alive.

    Example:
        middleware=[AsyncIO(), ..., AsyncShutdown(kafka_producer_factory.close, redis_client_factory.close)]
    """

    def __init__(self, *hooks: Callable[[], Awaitable[None]]):
        self.hooks = hooks

    def after_worker_shutdown(self, broker, worker):  # noqa: ARG002
        event_loop_thread = get_event_loop_thread()
        if event_loop_thread is None:  # `AsyncIO` is not in the list or has already stopped the loop
            raise RuntimeError('AsyncShutdown must be placed after AsyncIO in the broker middleware')
        for hook in self.hooks:
            event_loop_thread.run_coroutine(hook())
