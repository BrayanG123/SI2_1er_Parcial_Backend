"""Contratos de entrada y salida de usuarios."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class PerfilClienteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    direccion: str | None
    preferencias_json: dict[str, Any] | None


class RolRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    descripcion: str | None


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    nombres: str
    apellidos: str
    telefono: str | None
    activo: bool
    sucursal_id: UUID | None
    creado_en: datetime
    roles: list[RolRead]
    perfil_cliente: PerfilClienteRead | None


class RegistroClienteRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nombres: str = Field(min_length=2, max_length=120)
    apellidos: str = Field(min_length=2, max_length=120)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = Field(default=None, max_length=500)

    @field_validator("nombres", "apellidos")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Debe contener al menos dos caracteres.")
        return normalized


class UsuarioAdminCreate(RegistroClienteRequest):
    activo: bool = True
    sucursal_id: UUID | None = None
    roles: list[str] = Field(default_factory=lambda: ["cliente"], min_length=1)


class UsuarioUpdate(BaseModel):
    email: EmailStr | None = None
    nombres: str | None = Field(default=None, min_length=2, max_length=120)
    apellidos: str | None = Field(default=None, min_length=2, max_length=120)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = Field(default=None, max_length=500)
    activo: bool | None = None
    sucursal_id: UUID | None = None
    roles: list[str] | None = Field(default=None, min_length=1)


class UsuarioPage(BaseModel):
    items: list[UsuarioRead]
    page: int
    page_size: int
    total: int


class RolCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=50, pattern=r"^[a-z][a-z0-9_-]*$")
    descripcion: str | None = Field(default=None, max_length=255)


class RolUpdate(BaseModel):
    nombre: str | None = Field(
        default=None,
        min_length=2,
        max_length=50,
        pattern=r"^[a-z][a-z0-9_-]*$",
    )
    descripcion: str | None = Field(default=None, max_length=255)
