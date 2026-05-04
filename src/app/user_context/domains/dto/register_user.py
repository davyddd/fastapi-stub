from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class RegisterUserRequestDTO(BaseModel):
    email: EmailStr
    password: str


class RegisterUserResponseDTO(BaseModel):
    id: UUID
    email: EmailStr
    created_at: datetime | None = None
    updated_at: datetime | None = None
