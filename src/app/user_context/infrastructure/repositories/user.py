from sqlmodel import select

from dddesign.structure.infrastructure.repositories import Repository

from config.databases.postgres import Atomic

from app.user_context.domains.entities import UserEntity
from app.user_context.infrastructure.models import UserModel


class UserRepository(Repository):
    @staticmethod
    async def get_by_email(email: str) -> UserEntity | None:
        async with Atomic() as postgres_session:
            statement = select(UserModel).where(UserModel.email == email)
            result = await postgres_session.exec(statement)
            user_model = result.one_or_none()
            return user_model.to_entity() if user_model else None

    @staticmethod
    async def create(email: str, password_hash: str) -> UserEntity:
        async with Atomic() as postgres_session:
            user_model = UserModel(email=email, password_hash=password_hash)
            postgres_session.add(user_model)
            await postgres_session.flush()
            await postgres_session.refresh(user_model)
            return user_model.to_entity()


user_repository_impl = UserRepository()
