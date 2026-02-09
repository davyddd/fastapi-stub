import logging
import os

from starlette.types import ASGIApp, Receive, Scope, Send

from ddutils.object_getter import get_object_by_path

logger = logging.getLogger(__name__)
close_db_connections = get_object_by_path(os.getenv('DB_CONNECTIONS_CLOSER_PATH'))


class DBConnectionsCloserMiddleware:
    """
    Middleware responsible for closing database connections after each HTTP request.
    It dynamically resolves the DB cleanup function via the `DB_CONNECTIONS_CLOSER_PATH` environment variable.

    Important: This middleware is implemented as a pure ASGI middleware rather than using
    `starlette.middleware.base.BaseHTTPMiddleware`, because BaseHTTPMiddleware wraps `call_next`
    in a new asyncio.Task, which breaks context-dependent connection scoping (e.g., when using
    asyncio.current_task() as a scope key for scoped registries).
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        try:
            await self.app(scope, receive, send)
        finally:
            if close_db_connections:
                await close_db_connections()
            else:
                logger.error(
                    {
                        'message': (
                            'DB connection closer function is not defined. '
                            'Make sure the `DB_CONNECTIONS_CLOSER_PATH` environment variable is set correctly.'
                        )
                    }
                )
