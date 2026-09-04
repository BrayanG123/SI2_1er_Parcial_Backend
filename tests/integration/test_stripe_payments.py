"""Integración de Payment Intents y webhooks usando un adaptador Stripe falso."""

from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.payment_gateway.client import (
    GatewayConfirmation,
    GatewayInitiation,
    GatewayPaymentStatus,
    GatewayWebhookEvent,
    InvalidGatewayWebhookError,
)
from app.integrations.payment_gateway.factory import get_payment_gateway
from app.main import app
from app.modules.branches.models import Sucursal
from app.modules.catalog.models import VarianteProducto
from app.modules.inventory.models import Inventario
from app.modules.orders.models import Pedido
from app.modules.payments.models import Pago
from tests.integration.test_cart_orders import (
    add_to_cart,
    auth_identity,
    client,
    db,
    load_stock,
    sales_context,
)


class FakeStripeGateway:
    environment = "STRIPE"
    method = "STRIPE"
    currency = "bob"
    publishable_key = "pk_test_demo"
    supports_test_confirmation = False

    def __init__(self) -> None:
        self.reference = "pi_demo"
        self.webhook_status = GatewayPaymentStatus.APPROVED

    def initiate(self, *, order_id: UUID, amount: Decimal) -> GatewayInitiation:
        assert amount > 0
        self.reference = f"pi_{str(order_id).replace('-', '')}"
        return GatewayInitiation(
            reference=self.reference,
            client_secret=f"{self.reference}_secret_demo",
        )

    def resume(self, *, reference: str) -> GatewayInitiation:
        return GatewayInitiation(
            reference=reference, client_secret=f"{reference}_secret_demo"
        )

    def confirm(self, *, reference: str, approve: bool) -> GatewayConfirmation:
        raise AssertionError("Stripe no debe confirmarse desde el backend")

    def refund(
        self, *, reference: str, amount: Decimal, idempotency_key: str
    ) -> str:
        return f"re_{idempotency_key}_{reference}_{amount}"

    def parse_webhook(
        self, *, payload: bytes, signature: str | None
    ) -> GatewayWebhookEvent:
        if signature != "valid":
            raise InvalidGatewayWebhookError("Firma inválida.")
        return GatewayWebhookEvent(
            event_id="evt_demo",
            event_type=(
                "payment_intent.succeeded"
                if self.webhook_status == GatewayPaymentStatus.APPROVED
                else "payment_intent.canceled"
            ),
            reference=self.reference,
            status=self.webhook_status,
        )


def _stripe_order(
    client: TestClient,
    db: Session,
    sales_context: dict[str, object],
    *,
    suffix: str,
    quantity: int,
) -> tuple[dict, dict[str, str], FakeStripeGateway, Sucursal, VarianteProducto]:
    branch = sales_context["branch"]
    variants = sales_context["variants"]
    assert isinstance(branch, Sucursal) and isinstance(variants, list)
    variant = variants[0]
    assert isinstance(variant, VarianteProducto)
    _, admin_headers = auth_identity(
        client, db, "administrador", suffix=f"stripe-admin-{suffix}"
    )
    _, customer_headers = auth_identity(
        client, db, "cliente", suffix=f"stripe-customer-{suffix}"
    )
    load_stock(client, admin_headers, branch, [variant], quantity=3)
    add_to_cart(client, customer_headers, variant, quantity)
    order = client.post(
        "/api/v1/orders/checkout",
        headers=customer_headers,
        json={"sucursal_id": str(branch.id)},
    )
    assert order.status_code == 201, order.text
    gateway = FakeStripeGateway()
    app.dependency_overrides[get_payment_gateway] = lambda: gateway
    return order.json(), customer_headers, gateway, branch, variant


def test_stripe_session_is_resumable_and_success_webhook_is_authoritative(
    client: TestClient, db: Session, sales_context: dict[str, object]
) -> None:
    order, headers, gateway, _branch, _variant = _stripe_order(
        client, db, sales_context, suffix="approved", quantity=1
    )
    initiated = client.post(
        f"/api/v1/payments/orders/{order['id']}", headers=headers
    )
    assert initiated.status_code == 201, initiated.text
    payment = initiated.json()
    assert payment["metodo"] == "STRIPE"
    assert payment["monto"] == "80.00"
    assert payment["client_secret"].endswith("_secret_demo")
    assert payment["publishable_key"] == "pk_test_demo"
    assert payment["moneda"] == "BOB"

    resumed = client.post(
        f"/api/v1/payments/orders/{order['id']}", headers=headers
    )
    assert resumed.status_code == 201
    assert resumed.json()["id"] == payment["id"]
    assert resumed.json()["referencia_externa"] == payment["referencia_externa"]
    assert client.post(
        f"/api/v1/payments/{payment['id']}/confirm",
        headers=headers,
        json={"resultado_prueba": "APROBAR"},
    ).status_code == 409

    assert client.post(
        "/api/v1/payments/stripe/webhook", content=b"{}"
    ).status_code == 400
    webhook = client.post(
        "/api/v1/payments/stripe/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "valid"},
    )
    assert webhook.status_code == 200, webhook.text
    assert webhook.json()["procesado"] is True
    duplicate = client.post(
        "/api/v1/payments/stripe/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "valid"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["procesado"] is False
    db.expire_all()
    assert db.get(Pago, UUID(payment["id"])).estado == "APROBADO"  # type: ignore[union-attr]
    assert db.get(Pedido, UUID(order["id"])).estado == "PAGADO"  # type: ignore[union-attr]


def test_canceled_stripe_webhook_cancels_once_and_restores_inventory(
    client: TestClient, db: Session, sales_context: dict[str, object]
) -> None:
    order, headers, gateway, branch, variant = _stripe_order(
        client, db, sales_context, suffix="rejected", quantity=2
    )
    initiated = client.post(
        f"/api/v1/payments/orders/{order['id']}", headers=headers
    )
    assert initiated.status_code == 201, initiated.text
    gateway.webhook_status = GatewayPaymentStatus.REJECTED
    for processed in (True, False):
        webhook = client.post(
            "/api/v1/payments/stripe/webhook",
            content=b"{}",
            headers={"Stripe-Signature": "valid"},
        )
        assert webhook.status_code == 200, webhook.text
        assert webhook.json()["procesado"] is processed

    db.expire_all()
    payment = db.scalar(select(Pago).where(Pago.pedido_id == UUID(order["id"])))
    inventory = db.scalar(
        select(Inventario).where(
            Inventario.sucursal_id == branch.id,
            Inventario.variante_id == variant.id,
        )
    )
    assert payment is not None and payment.estado == "RECHAZADO"
    assert db.get(Pedido, UUID(order["id"])).estado == "CANCELADO"  # type: ignore[union-attr]
    assert inventory is not None and inventory.stock_fisico == 3
