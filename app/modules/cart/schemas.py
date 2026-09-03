"""Contratos de entrada y salida del carrito."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DetalleCarritoCreate(BaseModel):
    variante_id: UUID
    cantidad: int = Field(default=1, gt=0, le=100)


class DetalleCarritoUpdate(BaseModel):
    cantidad: int = Field(gt=0, le=100)


class DetalleCarritoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    variante_id: UUID
    producto_id: UUID
    producto_nombre: str
    sku: str
    talla: str
    color: str
    cantidad: int
    precio_unitario_estimado: Decimal
    subtotal_estimado: Decimal


class CarritoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    cliente_id: UUID
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
    detalles: list[DetalleCarritoRead]
    subtotal_estimado: Decimal
