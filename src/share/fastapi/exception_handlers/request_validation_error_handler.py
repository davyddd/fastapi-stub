from starlette.requests import Request
from starlette.responses import JSONResponse

from fastapi.exceptions import RequestValidationError

from dddesign.components.domains.dto import Errors
from dddesign.structure.domains.errors import BaseError, CollectionError


async def handle_request_validation_error(request: Request, exc: RequestValidationError):  # noqa: ARG001
    collection_error = CollectionError()
    for error in exc.errors():
        field_name: str | None = '.'.join(str(item) for item in error['loc'][1:]) or None
        error = BaseError(status_code=400, message=error['msg'], field_name=field_name)
        collection_error.add(error)

    errors = Errors.factory(collection_error)
    return JSONResponse(status_code=errors.status_code, content=errors.model_dump())
