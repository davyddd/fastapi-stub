from fastapi import APIRouter

from app.probe_context.applications.probe import probe_app_factory

router = APIRouter()


@router.get('/')
async def sentry_debug():
    await probe_app_factory.get().sentry_debug()
