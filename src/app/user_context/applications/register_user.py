from dddesign.structure.applications import Application, ApplicationFactory
from dddesign.structure.domains.errors import BaseError
from sqlalchemy.exc import IntegrityError

from app.user_context.domains.dto import RegisterUserRequestDTO, RegisterUserResponseDTO
from app.user_context.infrastructure.adapters import PasswordHasher, password_hasher_impl
from app.user_context.infrastructure.repositories import UserRepository, user_repository_impl


class RegisterUserApp(Application):
    repo: UserRepository = user_repository_impl
    password_hasher: PasswordHasher = password_hasher_impl

    async def execute(self, dto: RegisterUserRequestDTO) -> RegisterUserResponseDTO:
        user = await self.repo.get_by_email(dto.email)
        if user:
            raise BaseError(status_code=409, message='User with this email already exists', field_name='email')

        password_hash = self.password_hasher.hash(dto.password)
        try:
            user = await self.repo.create(email=dto.email, password_hash=password_hash)
        except IntegrityError as exc:
            raise BaseError(status_code=409, message='User with this email already exists', field_name='email') from exc
        return RegisterUserResponseDTO(id=user.id, email=user.email, created_at=user.created_at, updated_at=user.updated_at)


register_user_app_factory = ApplicationFactory[RegisterUserApp](application_class=RegisterUserApp)
