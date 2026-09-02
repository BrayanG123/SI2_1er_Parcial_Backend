"""Contratos de entrada y salida de ciudades y sucursales."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def optional_text(value: str | None) -> str | None:
    return value.strip() or None if value is not None else None


class CiudadBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    departamento: str | None = Field(default=None, max_length=120)

    @field_validator("nombre")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Debe contener al menos dos caracteres.")
        return value

    @field_validator("departamento")
    @classmethod
    def normalize_department(cls, value: str | None) -> str | None:
        return optional_text(value)


class CiudadCreate(CiudadBase):
    pass


class CiudadUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    departamento: str | None = Field(default=None, max_length=120)

    @field_validator("nombre")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Debe contener al menos dos caracteres.")
        return value

    @field_validator("departamento")
    @classmethod
    def normalize_department(cls, value: str | None) -> str | None:
        return optional_text(value)


class CiudadRead(CiudadBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class CiudadPage(BaseModel):
    items: list[CiudadRead]
    page: int
    page_size: int
    total: int


class SucursalBase(BaseModel):
    ciudad_id: UUID
    nombre: str = Field(min_length=2, max_length=120)
    direccion: str = Field(min_length=3, max_length=500)
    telefono: str | None = Field(default=None, max_length=30)
    horario_informativo: str = Field(min_length=2, max_length=255)
    activa: bool = True

    @field_validator("nombre", "direccion", "horario_informativo")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("El campo no puede estar vacío.")
        return value

    @field_validator("telefono")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        return optional_text(value)


class SucursalCreate(SucursalBase):
    pass


class SucursalUpdate(BaseModel):
    ciudad_id: UUID | None = None
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    direccion: str | None = Field(default=None, min_length=3, max_length=500)
    telefono: str | None = Field(default=None, max_length=30)
    horario_informativo: str | None = Field(default=None, min_length=2, max_length=255)
    activa: bool | None = None

    @field_validator("nombre", "direccion", "horario_informativo")
    @classmethod
    def normalize_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 2:
            raise ValueError("El campo no puede estar vacío.")
        return value

    @field_validator("telefono")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        return optional_text(value)


class SucursalRead(SucursalBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ciudad: CiudadRead


class SucursalPage(BaseModel):
    items: list[SucursalRead]
    page: int
    page_size: int
    total: int
