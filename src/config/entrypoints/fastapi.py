from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from dddesign.structure.domains.errors import BaseError, CollectionError

from config.databases.aerospike import aerospike_client_factory
from config.databases.clickhouse import clickhouse_client_factory
from config.databases.kafka import kafka_producer_factory
from config.databases.redis import redis_client_factory
from config.entrypoints.dramatiq import dramatiq_facade_impl
from config.logging.configure import configure_logging_handlers
from config.logging.log_properties import log_properties_registry
from config.settings import settings
from config.urls import router

from share.fastapi.exception_handlers import (
    handle_base_error,
    handle_collection_error,
    handle_http_exception,
    handle_request_validation_error,
)
from share.fastapi.middlewares import LogPropertiesManagerMiddleware, RequestResponseLoggingMiddleware, SentryTagsMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: ARG001
    yield
    # Runs after the server stopped accepting requests and the in-flight ones finished:
    # the producer's buffer only reaches Kafka while the process runs.
    await kafka_producer_factory.close()
    await redis_client_factory.close()
    await aerospike_client_factory.close()
    await clickhouse_client_factory.close()


app = FastAPI(title=settings.PROJECT_NAME, debug=settings.DEBUG, servers=[{'url': settings.SERVER_URL}], lifespan=lifespan)
app.include_router(router)

app.exception_handler(BaseError)(handle_base_error)
app.exception_handler(CollectionError)(handle_collection_error)
app.exception_handler(HTTPException)(handle_http_exception)
app.exception_handler(RequestValidationError)(handle_request_validation_error)

app.add_middleware(
    CORSMiddleware,  # ty: ignore[invalid-argument-type]
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.add_middleware(RequestResponseLoggingMiddleware)  # ty: ignore[invalid-argument-type]
app.add_middleware(
    SentryTagsMiddleware,  # ty: ignore[invalid-argument-type]
    log_properties_registry=log_properties_registry,
)
app.add_middleware(
    LogPropertiesManagerMiddleware,  # ty: ignore[invalid-argument-type]
    log_properties_registry=log_properties_registry,
)

dramatiq_facade_impl.setup_tasks()
configure_logging_handlers()
