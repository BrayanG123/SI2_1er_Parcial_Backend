"""Contratos de entrada y salida de reservas."""

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.branches.schemas import SucursalRead
from app.modules.reservations.models import EstadoReserva


class DetalleReservaCreate(BaseModel):
    variante_id: UUID
    cantidad: int = Field(gt=0, le=100)


class ReservaCreate(BaseModel):
    sucursal_id: UUID
    fecha_visita: date
    hora_aproximada: time | None = None
    detalles: list[DetalleReservaCreate] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def variants_must_be_unique(self) -> "ReservaCreate":
        ids = [item.variante_id for item in self.detalles]
        if len(ids) != len(set(ids)):
            raise ValueError("Cada variante debe aparecer una sola vez en la reserva.")
        return self


class ClienteReservaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nombres: str
    apellidos: str
    email: str


class DetalleReservaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    inventario_id: UUID
    variante_id: UUID
    producto_id: UUID
    producto_nombre: str
    sku: str
    talla: str
    color: str
    cantidad: int


class ReservaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    cliente_id: UUID
    sucursal_id: UUID
    estado: EstadoReserva
    fecha_visita: date
    hora_aproximada: time | None
    vence_en: datetime
    creada_en: datetime
    cancelada_en: datetime | None
    cliente: ClienteReservaRead
    sucursal: SucursalRead
    detalles: list[DetalleReservaRead]


class ReservaPage(BaseModel):
    items: list[ReservaRead]
    page: int
    page_size: int
    total: int


class TransicionReservaRequest(BaseModel):
    estado: EstadoReserva


class VencimientoResultado(BaseModel):
    vencidas: int
