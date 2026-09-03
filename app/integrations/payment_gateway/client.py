"""Contrato de pasarela y adaptador determinista para el ambiente de prueba."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4


class GatewayPaymentStatus(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class GatewayConfirmation:
    status: GatewayPaymentStatus


class PaymentGateway(Protocol):
    """Puerto independiente del proveedor real de pagos."""

    environment: str

    def initiate(self, *, order_id: UUID, amount: Decimal) -> str: ...

    def confirm(self, *, reference: str, approve: bool) -> GatewayConfirmation: ...

    def refund(self, *, reference: str, amount: Decimal) -> str: ...


class TestPaymentGateway:
    """Simulación local: nunca recibe tarjetas ni realiza operaciones financieras."""

    environment = "PRUEBA"

    def initiate(self, *, order_id: UUID, amount: Decimal) -> str:
        del amount
        return f"TEST-PAY-{order_id}-{uuid4().hex[:8]}"

    def confirm(self, *, reference: str, approve: bool) -> GatewayConfirmation:
        del reference
        return GatewayConfirmation(
            status=(
                GatewayPaymentStatus.APPROVED
                if approve
                else GatewayPaymentStatus.REJECTED
            )
        )

    def refund(self, *, reference: str, amount: Decimal) -> str:
        del reference, amount
        return f"TEST-REF-{uuid4()}"
