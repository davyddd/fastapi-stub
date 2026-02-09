from fastapi import APIRouter

from app.probe_context.infrastructure.urls import router as probe_router

router = APIRouter(prefix='/api/v1')
router.include_router(probe_router, prefix='/probe', tags=['Probe'])
