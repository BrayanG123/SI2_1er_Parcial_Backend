"""Endpoints administrativos de usuarios, roles y perfiles de cliente."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser
from app.modules.users.schemas import (
    RolCreate,
    RolRead,
    RolUpdate,
    UsuarioAdminCreate,
    UsuarioPage,
    UsuarioRead,
    UsuarioUpdate,
)
from app.modules.users.service import RoleService, UserService


users_router = APIRouter(prefix="/users", tags=["users"])
roles_router = APIRouter(prefix="/roles", tags=["roles"])


@users_router.get("", response_model=UsuarioPage)
def list_users(
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UsuarioPage:
    users, total = UserService(db).list_users(page=page, page_size=page_size)
    return UsuarioPage(
        items=[UsuarioRead.model_validate(user) for user in users],
        page=page,
        page_size=page_size,
        total=total,
    )


@users_router.post("", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UsuarioAdminCreate,
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> UsuarioRead:
    return UsuarioRead.model_validate(UserService(db).create_user(data))


@users_router.get("/{user_id}", response_model=UsuarioRead)
def get_user(
    user_id: UUID,
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> UsuarioRead:
    return UsuarioRead.model_validate(UserService(db).get_user(user_id))


@users_router.patch("/{user_id}", response_model=UsuarioRead)
def update_user(
    user_id: UUID,
    data: UsuarioUpdate,
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> UsuarioRead:
    return UsuarioRead.model_validate(UserService(db).update_user(user_id, data))


@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    if user_id == admin.id:
        from app.core.exceptions import ConflictError

        raise ConflictError("No puedes eliminar tu propia cuenta administrativa.")
    UserService(db).delete_user(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roles_router.get("", response_model=list[RolRead])
def list_roles(
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[RolRead]:
    return [RolRead.model_validate(role) for role in RoleService(db).list_roles()]


@roles_router.post("", response_model=RolRead, status_code=status.HTTP_201_CREATED)
def create_role(
    data: RolCreate,
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> RolRead:
    return RolRead.model_validate(RoleService(db).create_role(data))


@roles_router.patch("/{role_id}", response_model=RolRead)
def update_role(
    role_id: UUID,
    data: RolUpdate,
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> RolRead:
    return RolRead.model_validate(RoleService(db).update_role(role_id, data))


@roles_router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: UUID,
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    RoleService(db).delete_role(role_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
