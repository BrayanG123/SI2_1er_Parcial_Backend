"""Contrato común de pasarela y adaptador determinista de desarrollo."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4


class GatewayPaymentStatus(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PaymentGatewayError(Exception):
    """Fallo seguro de comunicar al servicio sin filtrar datos del proveedor."""


class InvalidGatewayWebhookError(PaymentGatewayError):
    """La firma o el cuerpo del webhook no superaron la verificación."""


@dataclass(frozen=True)
class GatewayInitiation:
    reference: str
    client_secret: str | None = None


@dataclass(frozen=True)
class GatewayConfirmation:
    status: GatewayPaymentStatus


@dataclass(frozen=True)
class GatewayWebhookEvent:
    event_id: str
    event_type: str
    reference: str | None
    status: GatewayPaymentStatus | None


class PaymentGateway(Protocol):
    """Puerto independiente de Stripe o del simulador local."""

    environment: str
    method: str
    currency: str
    publishable_key: str | None
    supports_test_confirmation: bool

    def initiate(self, *, order_id: UUID, amount: Decimal) -> GatewayInitiation: ...

    def resume(self, *, reference: str) -> GatewayInitiation: ...

    def confirm(self, *, reference: str, approve: bool) -> GatewayConfirmation: ...

    def refund(
        self, *, reference: str, amount: Decimal, idempotency_key: str
    ) -> str: ...

    def parse_webhook(self, *, payload: bytes, signature: str | None) -> GatewayWebhookEvent: ...


class TestPaymentGateway:
    """Simulación local: nunca recibe tarjetas ni realiza operaciones financieras."""

    environment = "PRUEBA"
    method = "PASARELA_PRUEBA"
    currency = "bob"
    publishable_key = None
    supports_test_confirmation = True

    def initiate(self, *, order_id: UUID, amount: Decimal) -> GatewayInitiation:
        del amount
        return GatewayInitiation(reference=f"TEST-PAY-{order_id}-{uuid4().hex[:8]}")

    def resume(self, *, reference: str) -> GatewayInitiation:
        return GatewayInitiation(reference=reference)

    def confirm(self, *, reference: str, approve: bool) -> GatewayConfirmation:
        del reference
        return GatewayConfirmation(
            status=(
                GatewayPaymentStatus.APPROVED
                if approve
                else GatewayPaymentStatus.REJECTED
            )
        )

    def refund(
        self, *, reference: str, amount: Decimal, idempotency_key: str
    ) -> str:
        del reference, amount, idempotency_key
        return f"TEST-REF-{uuid4()}"

    def parse_webhook(
        self, *, payload: bytes, signature: str | None
    ) -> GatewayWebhookEvent:
        del payload, signature
        raise InvalidGatewayWebhookError("El adaptador local no recibe webhooks.")
