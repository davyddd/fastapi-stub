from contextlib import asynccontextmanager


@asynccontextmanager
async def async_suppress(*exceptions: type[Exception]):
    try:  # noqa: SIM105
        yield
    except exceptions:
        pass
