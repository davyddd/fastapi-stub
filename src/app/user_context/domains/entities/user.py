from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserEntity(BaseModel):
    id: UUID
    email: EmailStr
    password_hash: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
