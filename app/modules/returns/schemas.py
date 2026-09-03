"""Contratos de entrada y salida de devoluciones."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.branches.schemas import SucursalRead
from app.modules.payments.schemas import ReembolsoRead
from app.modules.returns.models import EstadoDevolucion


class DetalleDevolucionCreate(BaseModel):
    detalle_pedido_id: UUID
    cantidad: int = Field(gt=0, le=100)
    motivo: str | None = Field(default=None, max_length=500)


class DevolucionCreate(BaseModel):
    pedido_id: UUID
    motivo_general: str | None = Field(default=None, max_length=500)
    detalles: list[DetalleDevolucionCreate] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_order_details(self) -> "DevolucionCreate":
        ids = [item.detalle_pedido_id for item in self.detalles]
        if len(ids) != len(set(ids)):
            raise ValueError("Cada detalle del pedido debe aparecer una sola vez.")
        return self


class TransicionDevolucionRequest(BaseModel):
    estado: EstadoDevolucion
    reingresar_stock: bool = True
    generar_reembolso: bool = True


class ClienteDevolucionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nombres: str
    apellidos: str
    email: str


class PedidoDevolucionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    numero: str
    sucursal: SucursalRead


class DetalleDevolucionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    detalle_pedido_id: UUID
    variante_id: UUID
    producto_nombre: str
    sku: str
    talla: str
    color: str
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal
    motivo: str | None


class DevolucionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    pedido_id: UUID
    cliente_id: UUID | None
    estado: EstadoDevolucion
    motivo_general: str | None
    reingresa_stock: bool | None
    genera_reembolso: bool | None
    monto_estimado: Decimal
    creada_en: datetime
    completada_en: datetime | None
    cliente: ClienteDevolucionRead | None
    pedido: PedidoDevolucionRead
    detalles: list[DetalleDevolucionRead]
    reembolso: ReembolsoRead | None


class DevolucionPage(BaseModel):
    items: list[DevolucionRead]
    page: int
    page_size: int
    total: int
