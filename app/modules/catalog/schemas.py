"""Contratos de entrada y salida del catálogo."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.modules.categories.schemas import CategoriaRead
from app.modules.suppliers.schemas import ProveedorRead


def clean_required(value: str) -> str:
    value = value.strip()
    if len(value) < 1:
        raise ValueError("El campo no puede estar vacío.")
    return value


def clean_optional(value: str | None) -> str | None:
    return value.strip() or None if value is not None else None


class TallaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=50)
    orden: int | None = Field(default=None, ge=0)

    @field_validator("nombre")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_required(value).upper()


class TallaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=50)
    orden: int | None = Field(default=None, ge=0)

    @field_validator("nombre")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return clean_required(value).upper() if value is not None else None


class TallaRead(TallaCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class ColorCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    codigo_hex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("nombre")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_required(value)

    @field_validator("codigo_hex")
    @classmethod
    def normalize_hex(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class ColorUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    codigo_hex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("nombre")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return clean_required(value) if value is not None else None

    @field_validator("codigo_hex")
    @classmethod
    def normalize_hex(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class ColorRead(ColorCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class TemporadaCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    activa: bool = True

    @field_validator("nombre")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_required(value)

    @model_validator(mode="after")
    def validate_dates(self) -> "TemporadaCreate":
        if self.fecha_inicio and self.fecha_fin and self.fecha_inicio > self.fecha_fin:
            raise ValueError("La fecha inicial no puede ser posterior a la fecha final.")
        return self


class TemporadaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    activa: bool | None = None

    @field_validator("nombre")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return clean_required(value) if value is not None else None


class TemporadaRead(TemporadaCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class ColeccionCreate(BaseModel):
    temporada_id: UUID
    nombre: str = Field(min_length=2, max_length=120)
    descripcion: str | None = Field(default=None, max_length=500)

    @field_validator("nombre")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_required(value)

    @field_validator("descripcion")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return clean_optional(value)


class ColeccionUpdate(BaseModel):
    temporada_id: UUID | None = None
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    descripcion: str | None = Field(default=None, max_length=500)


class ColeccionRead(ColeccionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    temporada: TemporadaRead


class VarianteCreate(BaseModel):
    talla_id: UUID
    color_id: UUID
    sku: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    precio: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    activa: bool = True

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        return value.strip().upper()


class VarianteUpdate(BaseModel):
    talla_id: UUID | None = None
    color_id: UUID | None = None
    sku: str | None = Field(default=None, min_length=2, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    precio: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    activa: bool | None = None

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None


class ImagenCreate(BaseModel):
    url: HttpUrl
    es_principal: bool = False
    orden: int = Field(default=0, ge=0)


class ImagenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    url: str
    es_principal: bool
    orden: int


class VarianteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    producto_id: UUID
    talla_id: UUID
    color_id: UUID
    sku: str
    precio: Decimal | None
    activa: bool
    talla: TallaRead
    color: ColorRead


class ProductoCreate(BaseModel):
    categoria_id: UUID
    proveedor_id: UUID
    temporada_id: UUID | None = None
    coleccion_id: UUID | None = None
    nombre: str = Field(min_length=2, max_length=180)
    descripcion: str | None = Field(default=None, max_length=1000)
    marca: str | None = Field(default=None, max_length=120)
    precio_base: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    activo: bool = True
    variantes: list[VarianteCreate] = Field(min_length=1)
    imagenes: list[ImagenCreate] = Field(default_factory=list, max_length=12)

    @field_validator("nombre")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_required(value)

    @field_validator("descripcion", "marca")
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return clean_optional(value)

    @model_validator(mode="after")
    def validate_nested_uniqueness(self) -> "ProductoCreate":
        combinations = {(item.talla_id, item.color_id) for item in self.variantes}
        skus = {item.sku for item in self.variantes}
        if len(combinations) != len(self.variantes):
            raise ValueError("No se puede repetir una combinación de talla y color.")
        if len(skus) != len(self.variantes):
            raise ValueError("No se puede repetir un SKU.")
        if sum(image.es_principal for image in self.imagenes) > 1:
            raise ValueError("Solo una imagen puede ser principal.")
        return self


class ProductoUpdate(BaseModel):
    categoria_id: UUID | None = None
    proveedor_id: UUID | None = None
    temporada_id: UUID | None = None
    coleccion_id: UUID | None = None
    nombre: str | None = Field(default=None, min_length=2, max_length=180)
    descripcion: str | None = Field(default=None, max_length=1000)
    marca: str | None = Field(default=None, max_length=120)
    precio_base: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    activo: bool | None = None
    imagenes: list[ImagenCreate] | None = Field(default=None, max_length=12)

    @model_validator(mode="after")
    def validate_main_image(self) -> "ProductoUpdate":
        if self.imagenes and sum(image.es_principal for image in self.imagenes) > 1:
            raise ValueError("Solo una imagen puede ser principal.")
        return self


class ProductoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    categoria_id: UUID
    proveedor_id: UUID
    temporada_id: UUID | None
    coleccion_id: UUID | None
    nombre: str
    descripcion: str | None
    marca: str | None
    precio_base: Decimal
    activo: bool
    categoria: CategoriaRead
    proveedor: ProveedorRead
    temporada: TemporadaRead | None
    coleccion: ColeccionRead | None
    variantes: list[VarianteRead]
    imagenes: list[ImagenRead]


class ProductoPage(BaseModel):
    items: list[ProductoRead]
    page: int
    page_size: int
    total: int
