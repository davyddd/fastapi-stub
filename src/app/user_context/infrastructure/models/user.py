from uuid import UUID, uuid4

from sqlalchemy import String, UniqueConstraint
from sqlmodel import Field

from app.user_context.domains.entities import UserEntity
from share.sqlmodel.models.base import BaseSQLModel
from share.sqlmodel.models.mixins.dates import DatesMixin


class UserModel(BaseSQLModel[UserEntity], DatesMixin, table=True):
    __table_args__ = (UniqueConstraint('email'),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(sa_type=String(254), nullable=False, index=True)
    password_hash: str = Field(sa_type=String(255), nullable=False)
