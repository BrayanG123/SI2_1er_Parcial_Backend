"""Contratos de entrada y salida de autenticación."""

from pydantic import BaseModel, EmailStr, Field

from app.modules.users.schemas import UsuarioRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UsuarioRead
