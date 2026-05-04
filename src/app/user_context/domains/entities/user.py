from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserEntity(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: UUID = Field(alias='id')
    email: EmailStr
    password_hash: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
