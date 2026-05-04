from dddesign.structure.applications import Application, ApplicationFactory
from dddesign.structure.domains.errors import BaseError

from app.user_context.domains.dto import LoginUserRequestDTO, LoginUserResponseDTO
from app.user_context.infrastructure.adapters import JWTProvider, PasswordHasher, jwt_provider_impl, password_hasher_impl
from app.user_context.infrastructure.repositories import UserRepository, user_repository_impl


class LoginUserApp(Application):
    repo: UserRepository = user_repository_impl
    password_hasher: PasswordHasher = password_hasher_impl
    jwt_provider: JWTProvider = jwt_provider_impl

    async def execute(self, dto: LoginUserRequestDTO) -> LoginUserResponseDTO:
        invalid_credentials_error = BaseError(status_code=401, message='Invalid credentials')

        user = await self.repo.get_by_email(dto.email)
        if not user:
            raise invalid_credentials_error

        is_valid_password = self.password_hasher.verify(dto.password, user.password_hash)
        if not is_valid_password:
            raise invalid_credentials_error

        access_token = self.jwt_provider.create_access_token(user.user_id)
        return LoginUserResponseDTO(access_token=access_token)


login_user_app_factory = ApplicationFactory[LoginUserApp](application_class=LoginUserApp)
