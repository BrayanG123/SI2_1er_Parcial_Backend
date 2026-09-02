"""Modelos ORM de usuarios, roles y perfiles de cliente."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class UsuarioRol(Base):
    __tablename__ = "usuario_roles"

    usuario_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        primary_key=True,
    )
    rol_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("roles.id", ondelete="RESTRICT"),
        primary_key=True,
    )


class Rol(Base):
    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    nombre: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    descripcion: Mapped[str | None] = mapped_column(String(255))

    usuarios: Mapped[list["Usuario"]] = relationship(
        secondary="usuario_roles",
        back_populates="roles",
    )


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (Index("ix_usuarios_email", "email", unique=True),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nombres: Mapped[str] = mapped_column(String(120), nullable=False)
    apellidos: Mapped[str] = mapped_column(String(120), nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(30))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sucursal_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("sucursales.id", ondelete="SET NULL"),
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    roles: Mapped[list[Rol]] = relationship(
        secondary="usuario_roles",
        back_populates="usuarios",
        lazy="selectin",
    )
    perfil_cliente: Mapped["PerfilCliente | None"] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan",
        lazy="selectin",
        uselist=False,
    )
    sucursal: Mapped["Sucursal | None"] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="empleados"
    )


class PerfilCliente(Base):
    __tablename__ = "perfiles_cliente"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    usuario_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    direccion: Mapped[str | None] = mapped_column(String(500))
    preferencias_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    usuario: Mapped[Usuario] = relationship(back_populates="perfil_cliente")
