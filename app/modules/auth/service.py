"""Casos de uso de autenticación; consulta las cuentas mediante `users`."""

from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, verify_password
from app.modules.auth.schemas import LoginRequest, TokenResponse
from app.modules.users.repository import UserRepository
from app.modules.users.service import normalize_email


class AuthService:
    def __init__(self, db: Session) -> None:
        self.users = UserRepository(db)

    def login(self, data: LoginRequest) -> TokenResponse:
        user = self.users.get_by_email(normalize_email(str(data.email)))
        if user is None or not verify_password(data.password, user.password_hash):
            raise AuthenticationError("Correo o contraseña incorrectos.")
        if not user.activo:
            raise AuthenticationError("La cuenta está desactivada.")
        return TokenResponse(access_token=create_access_token(user.id), user=user)
