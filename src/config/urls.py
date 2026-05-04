from fastapi import APIRouter

from app.probe_context.infrastructure.urls import router as probe_router
from app.user_context.infrastructure.urls import router as user_router

router = APIRouter(prefix='/api/v1')
router.include_router(probe_router, prefix='/probe', tags=['Probe'])
router.include_router(user_router, prefix='/user', tags=['User'])
