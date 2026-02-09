import logging
import os
from functools import wraps

from ddutils.object_getter import get_object_by_path

logger = logging.getLogger(__name__)
close_db_connections = get_object_by_path(os.getenv('DB_CONNECTIONS_CLOSER_PATH'))


def close_db_connections_decorator(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            await func(*args, **kwargs)
        finally:
            if close_db_connections:
                await close_db_connections()
            else:
                logger.error(
                    {
                        'message': (
                            'DB connection closer function is not defined. '
                            'Make sure the DB_CONNECTIONS_CLOSER_PATH environment variable is set correctly.'
                        )
                    }
                )

    return wrapper
