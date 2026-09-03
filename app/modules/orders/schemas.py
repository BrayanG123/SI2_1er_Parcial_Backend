"""Contratos de entrada y salida de pedidos."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.branches.schemas import SucursalRead
from app.modules.orders.models import CanalPedido, EstadoPedido


class LineaPedidoCreate(BaseModel):
    variante_id: UUID
    cantidad: int = Field(gt=0, le=100)


class LineasUnicasMixin(BaseModel):
    detalles: list[LineaPedidoCreate] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_variants(self) -> "LineasUnicasMixin":
        ids = [item.variante_id for item in self.detalles]
        if len(ids) != len(set(ids)):
            raise ValueError("Cada variante debe aparecer una sola vez.")
        return self


class CheckoutCarritoRequest(BaseModel):
    sucursal_id: UUID
    canal: Literal["WEB", "MOBILE"] = "WEB"


class CheckoutReservaRequest(LineasUnicasMixin):
    canal: Literal["WEB", "MOBILE"] = "WEB"


class VentaPosRequest(LineasUnicasMixin):
    sucursal_id: UUID
    cliente_id: UUID | None = None


class ClientePedidoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nombres: str
    apellidos: str
    email: str


class DetallePedidoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    variante_id: UUID
    producto_id: UUID
    producto_nombre: str
    sku: str
    talla: str
    color: str
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal


class PedidoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    numero: str
    cliente_id: UUID | None
    sucursal_id: UUID
    reserva_id: UUID | None
    canal: CanalPedido
    estado: EstadoPedido
    subtotal: Decimal
    descuento: Decimal
    total: Decimal
    creado_en: datetime
    cliente: ClientePedidoRead | None
    sucursal: SucursalRead
    detalles: list[DetallePedidoRead]


class PedidoPage(BaseModel):
    items: list[PedidoRead]
    page: int
    page_size: int
    total: int


class PedidoOptions(BaseModel):
    sucursales: list[SucursalRead]


class VariantePosRead(BaseModel):
    inventario_id: UUID
    sucursal_id: UUID
    sucursal_nombre: str
    variante_id: UUID
    producto_id: UUID
    producto_nombre: str
    sku: str
    talla: str
    color: str
    precio_unitario: Decimal
    stock_disponible: int


class PedidoFilters(BaseModel):
    canal: CanalPedido | None = None
    estado: EstadoPedido | None = None
    sucursal_id: UUID | None = None
    desde: date | None = None
    hasta: date | None = None
