"""Integración portable con la pasarela de pago."""

from app.integrations.payment_gateway.client import PaymentGateway, TestPaymentGateway
from app.integrations.payment_gateway.factory import get_payment_gateway
from app.integrations.payment_gateway.stripe_client import StripePaymentGateway

__all__ = [
    "PaymentGateway",
    "StripePaymentGateway",
    "TestPaymentGateway",
    "get_payment_gateway",
]
