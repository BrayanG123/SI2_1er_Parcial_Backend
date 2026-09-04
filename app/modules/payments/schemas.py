"""Contratos de entrada y salida de pagos."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.payments.models import EstadoPago, MetodoPago


class ConfirmacionPagoPruebaRequest(BaseModel):
    resultado_prueba: Literal["APROBAR", "RECHAZAR"]


class ReembolsoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    pago_id: UUID
    devolucion_id: UUID | None
    monto: Decimal
    motivo: str
    referencia_externa: str | None
    estado: Literal["COMPLETADO"]
    creado_en: datetime


class PagoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    pedido_id: UUID
    metodo: MetodoPago
    estado: EstadoPago
    monto: Decimal
    monto_reembolsado: Decimal
    referencia_externa: str | None
    ambiente: Literal["PRUEBA", "STRIPE", "LOCAL"]
    creado_en: datetime
    pagado_en: datetime | None
    reembolsos: list[ReembolsoRead]
    client_secret: str | None = None
    publishable_key: str | None = None
    moneda: str | None = None


class StripeWebhookRead(BaseModel):
    recibido: bool
    procesado: bool
    evento_id: str
