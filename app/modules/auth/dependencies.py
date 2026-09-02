"""Dependencias de FastAPI para obtener usuario y validar permisos."""

from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, ForbiddenError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.modules.users.models import Usuario
from app.modules.users.repository import UserRepository


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> Usuario:
    if credentials is None:
        raise AuthenticationError()
    try:
        user_id = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError() from exc

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise AuthenticationError()
    if not user.activo:
        raise AuthenticationError("La cuenta está desactivada.")
    return user


CurrentUser = Annotated[Usuario, Depends(get_current_user)]


def require_roles(*allowed_roles: str) -> Callable[[CurrentUser], Usuario]:
    allowed = set(allowed_roles)

    def dependency(current_user: CurrentUser) -> Usuario:
        current_roles = {role.nombre for role in current_user.roles}
        if current_roles.isdisjoint(allowed):
            raise ForbiddenError()
        return current_user

    return dependency


AdminUser = Annotated[Usuario, Depends(require_roles("administrador"))]
InventoryReader = Annotated[
    Usuario,
    Depends(require_roles("administrador", "encargado", "cajero")),
]
InventoryManager = Annotated[
    Usuario,
    Depends(require_roles("administrador", "encargado")),
]
