from pydantic import BaseModel, EmailStr


class LoginUserRequestDTO(BaseModel):
    email: EmailStr
    password: str


class LoginUserResponseDTO(BaseModel):
    access_token: str
    token_type: str = 'bearer'
