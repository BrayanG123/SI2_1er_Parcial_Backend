"""Pruebas del adaptador Stripe sin realizar solicitudes de red."""

from decimal import Decimal
import hashlib
import hmac
from types import SimpleNamespace
import time
from uuid import uuid4

import pytest

from app.integrations.payment_gateway.client import (
    GatewayPaymentStatus,
    InvalidGatewayWebhookError,
)
from app.integrations.payment_gateway.stripe_client import StripePaymentGateway


class FakeStripeClient:
    def __init__(self) -> None:
        self.intent_creations: list[tuple[dict, dict]] = []
        self.intent_retrievals: list[str] = []
        self.refund_creations: list[tuple[dict, dict]] = []
        self.event = {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_123"}},
        }
        self.v1 = SimpleNamespace(
            payment_intents=SimpleNamespace(
                create=self.create_intent,
                retrieve=self.retrieve_intent,
            ),
            refunds=SimpleNamespace(create=self.create_refund),
        )

    def create_intent(self, params: dict, options: dict) -> SimpleNamespace:
        self.intent_creations.append((params, options))
        return SimpleNamespace(id="pi_123", client_secret="pi_123_secret_demo")

    def retrieve_intent(self, reference: str) -> SimpleNamespace:
        self.intent_retrievals.append(reference)
        return SimpleNamespace(id=reference, client_secret=f"{reference}_secret_demo")

    def create_refund(self, params: dict, options: dict) -> SimpleNamespace:
        self.refund_creations.append((params, options))
        return SimpleNamespace(id="re_123")

    def construct_event(self, payload: bytes, signature: str, secret: str) -> dict:
        assert payload == b"{}"
        assert signature == "signed"
        assert secret == "whsec_demo"
        return self.event


def _gateway(client: FakeStripeClient) -> StripePaymentGateway:
    return StripePaymentGateway(
        secret_key="sk_test_demo",
        webhook_secret="whsec_demo",
        publishable_key="pk_test_demo",
        client=client,  # type: ignore[arg-type]
    )


def test_stripe_intent_uses_bob_minor_units_metadata_and_idempotency() -> None:
    client = FakeStripeClient()
    gateway = _gateway(client)
    order_id = uuid4()

    initiation = gateway.initiate(order_id=order_id, amount=Decimal("123.45"))

    assert initiation.reference == "pi_123"
    assert initiation.client_secret == "pi_123_secret_demo"
    params, options = client.intent_creations[0]
    assert params["amount"] == 12345
    assert params["currency"] == "bob"
    assert params["payment_method_types"] == ["card"]
    assert params["metadata"] == {"order_id": str(order_id)}
    assert options["idempotency_key"] == f"payment-intent:{order_id}"


def test_stripe_resumes_intent_refunds_and_verifies_webhook() -> None:
    client = FakeStripeClient()
    gateway = _gateway(client)

    resumed = gateway.resume(reference="pi_existing")
    refund = gateway.refund(
        reference="pi_existing",
        amount=Decimal("80.00"),
        idempotency_key="refund:return-1",
    )
    event = gateway.parse_webhook(payload=b"{}", signature="signed")

    assert resumed.client_secret == "pi_existing_secret_demo"
    assert client.intent_retrievals == ["pi_existing"]
    assert refund == "re_123"
    assert client.refund_creations[0] == (
        {"payment_intent": "pi_existing", "amount": 8000},
        {"idempotency_key": "refund:return-1"},
    )
    assert event.reference == "pi_123"
    assert event.status == GatewayPaymentStatus.APPROVED
    client.event["type"] = "payment_intent.payment_failed"
    assert gateway.parse_webhook(payload=b"{}", signature="signed").status is None
    client.event["type"] = "payment_intent.canceled"
    assert (
        gateway.parse_webhook(payload=b"{}", signature="signed").status
        == GatewayPaymentStatus.REJECTED
    )
    with pytest.raises(InvalidGatewayWebhookError):
        gateway.parse_webhook(payload=b"{}", signature=None)


def test_stripe_sdk_rejects_tampering_and_accepts_a_valid_signature() -> None:
    secret = "whsec_demo"
    payload = (
        b'{"id":"evt_signed","type":"payment_intent.succeeded",'
        b'"data":{"object":{"id":"pi_signed"}}}'
    )
    timestamp = str(int(time.time()))
    digest = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    gateway = StripePaymentGateway(
        secret_key="sk_test_demo",
        webhook_secret=secret,
        publishable_key="pk_test_demo",
    )

    event = gateway.parse_webhook(
        payload=payload,
        signature=f"t={timestamp},v1={digest}",
    )

    assert event.event_id == "evt_signed"
    assert event.reference == "pi_signed"
    assert event.status == GatewayPaymentStatus.APPROVED
    with pytest.raises(InvalidGatewayWebhookError):
        gateway.parse_webhook(
            payload=payload + b" ",
            signature=f"t={timestamp},v1={digest}",
        )
