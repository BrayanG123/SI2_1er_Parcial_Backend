"""Casos de uso de usuarios y asignación de roles."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConfigurationError, ConflictError, NotFoundError
from app.core.security import hash_password
from app.modules.branches.repository import BranchRepository
from app.modules.users.models import PerfilCliente, Rol, Usuario
from app.modules.users.repository import RoleRepository, UserRepository
from app.modules.users.schemas import (
    RegistroClienteRequest,
    RolCreate,
    RolUpdate,
    UsuarioAdminCreate,
    UsuarioUpdate,
)


PROTECTED_ROLE_NAMES = {"cliente", "administrador", "encargado", "cajero"}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_role_names(names: list[str]) -> set[str]:
    return {name.strip().lower() for name in names if name.strip()}


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.roles = RoleRepository(db)
        self.branches = BranchRepository(db)

    def register_client(self, data: RegistroClienteRequest) -> Usuario:
        return self._create_user(data, role_names={"cliente"}, active=True, branch_id=None)

    def create_user(self, data: UsuarioAdminCreate) -> Usuario:
        return self._create_user(
            data,
            role_names=normalize_role_names(data.roles),
            active=data.activo,
            branch_id=data.sucursal_id,
        )

    def _create_user(
        self,
        data: RegistroClienteRequest,
        *,
        role_names: set[str],
        active: bool,
        branch_id: UUID | None,
    ) -> Usuario:
        self._validate_branch(branch_id)
        email = normalize_email(str(data.email))
        if self.users.get_by_email(email):
            raise ConflictError("Ya existe una cuenta registrada con ese correo.")

        roles = self._resolve_roles(role_names)
        profile = (
            PerfilCliente(direccion=data.direccion, preferencias_json=None)
            if "cliente" in role_names or data.direccion
            else None
        )
        user = Usuario(
            email=email,
            password_hash=hash_password(data.password),
            nombres=data.nombres.strip(),
            apellidos=data.apellidos.strip(),
            telefono=data.telefono.strip() if data.telefono else None,
            activo=active,
            sucursal_id=branch_id,
            roles=roles,
            perfil_cliente=profile,
        )
        self.users.add(user)
        return self._commit_and_reload(user, "No se pudo registrar el usuario.")

    def get_user(self, user_id: UUID) -> Usuario:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado.")
        return user

    def list_users(self, *, page: int, page_size: int) -> tuple[list[Usuario], int]:
        return self.users.list(offset=(page - 1) * page_size, limit=page_size)

    def update_user(self, user_id: UUID, data: UsuarioUpdate) -> Usuario:
        user = self.get_user(user_id)
        fields = data.model_fields_set

        if "email" in fields and data.email is not None:
            email = normalize_email(str(data.email))
            duplicate = self.users.get_by_email(email)
            if duplicate and duplicate.id != user.id:
                raise ConflictError("Ya existe una cuenta registrada con ese correo.")
            user.email = email
        if "nombres" in fields and data.nombres is not None:
            user.nombres = data.nombres.strip()
        if "apellidos" in fields and data.apellidos is not None:
            user.apellidos = data.apellidos.strip()
        if "telefono" in fields:
            user.telefono = data.telefono.strip() if data.telefono else None
        if "activo" in fields and data.activo is not None:
            user.activo = data.activo
        if "sucursal_id" in fields:
            self._validate_branch(data.sucursal_id)
            user.sucursal_id = data.sucursal_id
        if "roles" in fields and data.roles is not None:
            user.roles = self._resolve_roles(normalize_role_names(data.roles))
        if "direccion" in fields:
            if user.perfil_cliente is None:
                user.perfil_cliente = PerfilCliente(direccion=data.direccion)
            else:
                user.perfil_cliente.direccion = data.direccion

        return self._commit_and_reload(user, "No se pudo actualizar el usuario.")

    def delete_user(self, user_id: UUID) -> None:
        user = self.get_user(user_id)
        self.users.delete(user)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("El usuario tiene información relacionada y no puede eliminarse.") from exc

    def _resolve_roles(self, role_names: set[str]) -> list[Rol]:
        if not role_names:
            raise ConflictError("El usuario debe tener al menos un rol.")
        roles = self.roles.get_by_names(role_names)
        found_names = {role.nombre for role in roles}
        missing = sorted(role_names - found_names)
        if missing:
            raise ConfigurationError(f"No existen los roles requeridos: {', '.join(missing)}.")
        return roles

    def _validate_branch(self, branch_id: UUID | None) -> None:
        if branch_id is None:
            return
        branch = self.branches.get_by_id(branch_id)
        if branch is None:
            raise NotFoundError("Sucursal no encontrada.")
        if not branch.activa:
            raise ConflictError("No se puede asignar un usuario a una sucursal inactiva.")

    def _commit_and_reload(self, user: Usuario, error_message: str) -> Usuario:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(error_message) from exc
        return self.get_user(user.id)


class RoleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.roles = RoleRepository(db)

    def list_roles(self) -> list[Rol]:
        return self.roles.list()

    def create_role(self, data: RolCreate) -> Rol:
        name = data.nombre.strip().lower()
        if self.roles.get_by_name(name):
            raise ConflictError("Ya existe un rol con ese nombre.")
        role = Rol(nombre=name, descripcion=data.descripcion)
        self.roles.add(role)
        return self._commit(role)

    def update_role(self, role_id: UUID, data: RolUpdate) -> Rol:
        role = self._get_role(role_id)
        if data.nombre is not None:
            name = data.nombre.strip().lower()
            if role.nombre in PROTECTED_ROLE_NAMES and name != role.nombre:
                raise ConflictError("Los roles iniciales no pueden renombrarse.")
            duplicate = self.roles.get_by_name(name)
            if duplicate and duplicate.id != role.id:
                raise ConflictError("Ya existe un rol con ese nombre.")
            role.nombre = name
        if "descripcion" in data.model_fields_set:
            role.descripcion = data.descripcion
        return self._commit(role)

    def delete_role(self, role_id: UUID) -> None:
        role = self._get_role(role_id)
        if role.nombre in PROTECTED_ROLE_NAMES:
            raise ConflictError("Los roles iniciales no pueden eliminarse.")
        if self.roles.assigned_user_count(role.id):
            raise ConflictError("No se puede eliminar un rol asignado a usuarios.")
        self.roles.delete(role)
        self.db.commit()

    def _get_role(self, role_id: UUID) -> Rol:
        role = self.roles.get_by_id(role_id)
        if role is None:
            raise NotFoundError("Rol no encontrado.")
        return role

    def _commit(self, role: Rol) -> Rol:
        try:
            self.db.commit()
            self.db.refresh(role)
            return role
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("No se pudo guardar el rol.") from exc
