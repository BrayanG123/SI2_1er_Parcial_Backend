"""Persistencia de usuarios, roles y perfiles de cliente."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.users.models import Rol, Usuario


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: UUID) -> Usuario | None:
        statement = (
            select(Usuario)
            .where(Usuario.id == user_id)
            .options(selectinload(Usuario.roles), selectinload(Usuario.perfil_cliente))
        )
        return self.db.scalar(statement)

    def get_by_email(self, email: str) -> Usuario | None:
        statement = (
            select(Usuario)
            .where(Usuario.email == email)
            .options(selectinload(Usuario.roles), selectinload(Usuario.perfil_cliente))
        )
        return self.db.scalar(statement)

    def list(self, *, offset: int, limit: int) -> tuple[list[Usuario], int]:
        statement = (
            select(Usuario)
            .order_by(Usuario.creado_en.desc())
            .offset(offset)
            .limit(limit)
            .options(selectinload(Usuario.roles), selectinload(Usuario.perfil_cliente))
        )
        users = list(self.db.scalars(statement).unique())
        total = self.db.scalar(select(func.count()).select_from(Usuario)) or 0
        return users, total

    def add(self, user: Usuario) -> Usuario:
        self.db.add(user)
        return user

    def delete(self, user: Usuario) -> None:
        self.db.delete(user)


class RoleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, role_id: UUID) -> Rol | None:
        return self.db.get(Rol, role_id)

    def get_by_name(self, name: str) -> Rol | None:
        return self.db.scalar(select(Rol).where(Rol.nombre == name))

    def get_by_names(self, names: set[str]) -> list[Rol]:
        if not names:
            return []
        return list(self.db.scalars(select(Rol).where(Rol.nombre.in_(names))))

    def list(self) -> list[Rol]:
        return list(self.db.scalars(select(Rol).order_by(Rol.nombre)))

    def add(self, role: Rol) -> Rol:
        self.db.add(role)
        return role

    def delete(self, role: Rol) -> None:
        self.db.delete(role)

    def assigned_user_count(self, role_id: UUID) -> int:
        from app.modules.users.models import UsuarioRol

        statement = select(func.count()).select_from(UsuarioRol).where(UsuarioRol.rol_id == role_id)
        return self.db.scalar(statement) or 0
