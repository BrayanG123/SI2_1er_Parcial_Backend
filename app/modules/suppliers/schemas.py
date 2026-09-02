"""Contratos de entrada y salida de proveedores."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def optional_text(value: str | None) -> str | None:
    return value.strip() or None if value is not None else None


class ProveedorBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=160)
    nit: str | None = Field(default=None, max_length=50)
    telefono: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    direccion: str | None = Field(default=None, max_length=500)
    activo: bool = True

    @field_validator("nombre")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Debe contener al menos dos caracteres.")
        return value

    @field_validator("nit", "telefono", "direccion")
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return optional_text(value)


class ProveedorCreate(ProveedorBase):
    pass


class ProveedorUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=160)
    nit: str | None = Field(default=None, max_length=50)
    telefono: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    direccion: str | None = Field(default=None, max_length=500)
    activo: bool | None = None

    @field_validator("nombre")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Debe contener al menos dos caracteres.")
        return value

    @field_validator("nit", "telefono", "direccion")
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return optional_text(value)


class ProveedorRead(ProveedorBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class ProveedorPage(BaseModel):
    items: list[ProveedorRead]
    page: int
    page_size: int
    total: int
