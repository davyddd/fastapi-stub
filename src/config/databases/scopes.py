import asyncio
import os


def process_loop_scope() -> tuple[int, asyncio.AbstractEventLoop]:
    """
    Scope key for a client that is a pool bound to its event loop (`redis.asyncio`, `aiokafka`): one client per
    process and loop. A second loop in the same process (a script running `asyncio.run` twice, a test suite)
    gets its own client instead of a "attached to a different loop" error, and the pid guards a forked child,
    whose inherited sockets must not be reused. Every entrypoint runs one loop per process (uvicorn, the dramatiq
    event-loop thread), so in practice this is one client per process.
    """
    return os.getpid(), asyncio.get_running_loop()
