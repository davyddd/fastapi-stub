from fastapi import APIRouter

from app.user_context.applications import register_user_app_factory
from app.user_context.domains.dto import RegisterUserRequestDTO, RegisterUserResponseDTO

router = APIRouter()


@router.post('/register', response_model=RegisterUserResponseDTO)
async def register_user(dto: RegisterUserRequestDTO) -> RegisterUserResponseDTO:
    return await register_user_app_factory.get().execute(dto)
