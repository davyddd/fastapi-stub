from starlette.requests import Request
from starlette.responses import JSONResponse

from dddesign.components.domains.dto import Errors
from dddesign.structure.domains.errors import CollectionError


async def handle_collection_error(request: Request, exc: CollectionError):  # noqa: ARG001
    errors = Errors.factory(exc)
    return JSONResponse(status_code=errors.status_code, content=errors.model_dump())
