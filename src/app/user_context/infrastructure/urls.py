from fastapi import APIRouter

from app.user_context.infrastructure.ports import http

router = APIRouter()
router.include_router(http.register_router)
router.include_router(http.login_router)
