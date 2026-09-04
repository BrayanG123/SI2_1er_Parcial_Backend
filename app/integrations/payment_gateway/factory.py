"""Construcción del adaptador de pago configurado para el ambiente."""

from app.core.config import get_settings
from app.core.exceptions import ConfigurationError
from app.integrations.payment_gateway.client import PaymentGateway, TestPaymentGateway
from app.integrations.payment_gateway.stripe_client import StripePaymentGateway


def get_payment_gateway() -> PaymentGateway:
    settings = get_settings()
    if settings.payment_gateway_provider == "test":
        return TestPaymentGateway()

    secret_key = (
        settings.stripe_secret_key.get_secret_value()
        if settings.stripe_secret_key is not None
        else ""
    )
    webhook_secret = (
        settings.stripe_webhook_secret.get_secret_value()
        if settings.stripe_webhook_secret is not None
        else ""
    )
    publishable_key = (settings.stripe_publishable_key or "").strip()
    if not secret_key.startswith("sk_"):
        raise ConfigurationError("STRIPE_SECRET_KEY no está configurada correctamente.")
    if not webhook_secret.startswith("whsec_"):
        raise ConfigurationError("STRIPE_WEBHOOK_SECRET no está configurada correctamente.")
    if not publishable_key.startswith("pk_"):
        raise ConfigurationError("STRIPE_PUBLISHABLE_KEY no está configurada correctamente.")
    return StripePaymentGateway(
        secret_key=secret_key,
        webhook_secret=webhook_secret,
        publishable_key=publishable_key,
    )
