from starlette.requests import Request
from starlette.responses import JSONResponse

from fastapi import HTTPException

from dddesign.components.domains.dto import Errors
from dddesign.structure.domains.errors import BaseError, CollectionError


async def handle_http_exception(request: Request, exc: HTTPException):  # noqa: ARG001
    error = BaseError(status_code=exc.status_code, message=exc.detail)
    collection_error = CollectionError()
    collection_error.add(error)

    errors = Errors.factory(collection_error)
    return JSONResponse(status_code=errors.status_code, content=errors.model_dump())
