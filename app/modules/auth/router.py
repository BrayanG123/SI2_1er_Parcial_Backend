"""Endpoints de registro, inicio de sesión y sesión actual."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.schemas import LoginRequest, TokenResponse
from app.modules.auth.service import AuthService
from app.modules.users.schemas import RegistroClienteRequest, UsuarioRead
from app.modules.users.service import UserService


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
def register_client(
    data: RegistroClienteRequest,
    db: Annotated[Session, Depends(get_db)],
) -> UsuarioRead:
    return UsuarioRead.model_validate(UserService(db).register_client(data))


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    return AuthService(db).login(data)


@router.get("/me", response_model=UsuarioRead)
def current_user(user: CurrentUser) -> UsuarioRead:
    return UsuarioRead.model_validate(user)
