"""Contratos de entrada y salida de categorías."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoriaBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    descripcion: str | None = Field(default=None, max_length=500)
    activa: bool = True

    @field_validator("nombre")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Debe contener al menos dos caracteres.")
        return value

    @field_validator("descripcion")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class CategoriaCreate(CategoriaBase):
    pass


class CategoriaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    descripcion: str | None = Field(default=None, max_length=500)
    activa: bool | None = None

    @field_validator("nombre")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Debe contener al menos dos caracteres.")
        return value

    @field_validator("descripcion")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class CategoriaRead(CategoriaBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class CategoriaPage(BaseModel):
    items: list[CategoriaRead]
    page: int
    page_size: int
    total: int
