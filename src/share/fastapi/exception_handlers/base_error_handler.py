from starlette.requests import Request
from starlette.responses import JSONResponse

from dddesign.components.domains.dto import Errors
from dddesign.structure.domains.errors import BaseError, CollectionError


async def handle_base_error(request: Request, exc: BaseError):  # noqa: ARG001
    collection_error = CollectionError()
    collection_error.add(exc)

    errors = Errors.factory(collection_error)
    return JSONResponse(status_code=errors.status_code, content=errors.model_dump())
