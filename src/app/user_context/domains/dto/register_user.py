from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterUserRequestDTO(BaseModel):
    email: EmailStr
    password: str


class RegisterUserResponseDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: UUID = Field(alias='id')
    email: EmailStr
    created_at: datetime | None = None
    updated_at: datetime | None = None
