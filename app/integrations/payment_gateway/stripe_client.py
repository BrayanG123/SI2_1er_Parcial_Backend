"""Adaptador Stripe basado en Payment Intents y webhooks firmados."""

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

import stripe

from app.integrations.payment_gateway.client import (
    GatewayConfirmation,
    GatewayInitiation,
    GatewayPaymentStatus,
    GatewayWebhookEvent,
    InvalidGatewayWebhookError,
    PaymentGatewayError,
)


class StripePaymentGateway:
    environment = "STRIPE"
    method = "STRIPE"
    currency = "bob"
    supports_test_confirmation = False

    def __init__(
        self,
        *,
        secret_key: str,
        webhook_secret: str,
        publishable_key: str,
        client: stripe.StripeClient | None = None,
    ) -> None:
        self.webhook_secret = webhook_secret
        self.publishable_key = publishable_key
        self.client = client or stripe.StripeClient(secret_key, max_network_retries=2)

    def initiate(self, *, order_id: UUID, amount: Decimal) -> GatewayInitiation:
        try:
            intent = self.client.v1.payment_intents.create(
                params={
                    "amount": self._minor_units(amount),
                    "currency": self.currency,
                    "payment_method_types": ["card"],
                    "metadata": {"order_id": str(order_id)},
                    "description": f"Pedido {order_id}",
                },
                options={"idempotency_key": f"payment-intent:{order_id}"},
            )
        except stripe.StripeError as exc:
            raise PaymentGatewayError("Stripe no pudo iniciar el pago.") from exc
        if not intent.id or not intent.client_secret:
            raise PaymentGatewayError("Stripe no devolvió una sesión de pago válida.")
        return GatewayInitiation(reference=intent.id, client_secret=intent.client_secret)

    def resume(self, *, reference: str) -> GatewayInitiation:
        try:
            intent = self.client.v1.payment_intents.retrieve(reference)
        except stripe.StripeError as exc:
            raise PaymentGatewayError("Stripe no pudo recuperar la sesión de pago.") from exc
        if not intent.id or not intent.client_secret:
            raise PaymentGatewayError("Stripe no devolvió una sesión de pago válida.")
        return GatewayInitiation(reference=intent.id, client_secret=intent.client_secret)

    def confirm(self, *, reference: str, approve: bool) -> GatewayConfirmation:
        del reference, approve
        raise PaymentGatewayError("Los pagos Stripe se confirman mediante Stripe.js y webhook.")

    def refund(
        self, *, reference: str, amount: Decimal, idempotency_key: str
    ) -> str:
        try:
            refund = self.client.v1.refunds.create(
                params={
                    "payment_intent": reference,
                    "amount": self._minor_units(amount),
                },
                options={"idempotency_key": idempotency_key},
            )
        except stripe.StripeError as exc:
            raise PaymentGatewayError("Stripe no pudo registrar el reembolso.") from exc
        if not refund.id:
            raise PaymentGatewayError("Stripe no devolvió una referencia de reembolso.")
        return refund.id

    def parse_webhook(
        self, *, payload: bytes, signature: str | None
    ) -> GatewayWebhookEvent:
        if not signature:
            raise InvalidGatewayWebhookError("Falta la firma Stripe-Signature.")
        try:
            event = self.client.construct_event(payload, signature, self.webhook_secret)
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise InvalidGatewayWebhookError("La firma del webhook de Stripe no es válida.") from exc

        event_type = str(event["type"])
        stripe_object = event["data"]["object"]
        try:
            reference = stripe_object["id"]
        except (KeyError, TypeError):
            reference = None
        status = None
        if event_type == "payment_intent.succeeded":
            status = GatewayPaymentStatus.APPROVED
        elif event_type == "payment_intent.canceled":
            status = GatewayPaymentStatus.REJECTED
        return GatewayWebhookEvent(
            event_id=str(event["id"]),
            event_type=event_type,
            reference=str(reference) if reference else None,
            status=status,
        )

    @staticmethod
    def _minor_units(amount: Decimal) -> int:
        return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
