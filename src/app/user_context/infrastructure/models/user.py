from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from share.sqlmodel.models.base import BaseSQLModel
from share.sqlmodel.models.mixins.dates import DatesMixin

from app.user_context.domains.entities import UserEntity


class UserModel(BaseSQLModel[UserEntity], DatesMixin, table=True):
    __table_args__ = (UniqueConstraint('email'),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)  # noqa: A003
    email: str = Field(max_length=254, nullable=False, index=True)
    password_hash: str = Field(max_length=255, nullable=False)
