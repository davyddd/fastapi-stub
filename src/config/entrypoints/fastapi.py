from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from dddesign.structure.domains.errors import BaseError, CollectionError

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

app = FastAPI(title=settings.PROJECT_NAME, debug=settings.DEBUG, servers=[{'url': settings.SERVER_URL}])
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
