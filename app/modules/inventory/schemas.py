"""Contratos de entrada y salida de inventario."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.branches.schemas import SucursalRead
from app.modules.catalog.schemas import ProductoRead, VarianteRead
from app.modules.inventory.models import TipoMovimiento


class EstadoStock(StrEnum):
    DISPONIBLE = "DISPONIBLE"
    BAJO = "BAJO"
    AGOTADO = "AGOTADO"


class ProductoInventarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nombre: str
    marca: str | None
    activo: bool


class InventarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sucursal_id: UUID
    variante_id: UUID
    stock_fisico: int
    stock_reservado: int
    stock_disponible: int
    actualizado_en: datetime
    sucursal: SucursalRead
    variante: VarianteRead
    producto: ProductoInventarioRead


class InventarioPage(BaseModel):
    items: list[InventarioRead]
    page: int
    page_size: int
    total: int


class MovimientoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    inventario_id: UUID
    tipo: TipoMovimiento
    cantidad: int
    referencia_tipo: str | None
    referencia_id: UUID | None
    observacion: str | None
    creado_en: datetime


class MovimientoPage(BaseModel):
    items: list[MovimientoRead]
    page: int
    page_size: int
    total: int


class RecepcionCreate(BaseModel):
    sucursal_id: UUID
    variante_id: UUID
    cantidad: int = Field(gt=0, le=1_000_000)
    observacion: str | None = Field(default=None, max_length=500)

    @field_validator("observacion")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class AjusteCreate(BaseModel):
    sucursal_id: UUID
    variante_id: UUID
    cantidad: int = Field(ge=-1_000_000, le=1_000_000)
    motivo: str = Field(min_length=3, max_length=500)

    @field_validator("cantidad")
    @classmethod
    def non_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("El ajuste no puede ser cero.")
        return value

    @field_validator("motivo")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("El motivo debe tener al menos tres caracteres.")
        return value


class DisponibilidadSucursalRead(BaseModel):
    sucursal_id: UUID
    sucursal_nombre: str
    ciudad_nombre: str
    variante_id: UUID
    talla: str
    color: str
    sku: str
    stock_disponible: int


class InventarioOptions(BaseModel):
    sucursales: list[SucursalRead]
    productos: list[ProductoRead]
