from fastapi import APIRouter

from app.user_context.applications import login_user_app_factory
from app.user_context.domains.dto import LoginUserRequestDTO, LoginUserResponseDTO

router = APIRouter()


@router.post('/login', response_model=LoginUserResponseDTO)
async def login_user(dto: LoginUserRequestDTO) -> LoginUserResponseDTO:
    return await login_user_app_factory.get().execute(dto)
