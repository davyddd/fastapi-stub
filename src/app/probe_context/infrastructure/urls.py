from fastapi import APIRouter

from app.probe_context.infrastructure.ports import http

router = APIRouter()
router.include_router(http.liveness_router, prefix='/liveness')
router.include_router(http.readiness_router, prefix='/readiness')
router.include_router(http.sentry_debug_router, prefix='/sentry-debug')
