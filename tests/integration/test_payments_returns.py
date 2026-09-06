from collections.abc import Generator
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.integrations.payment_gateway.client import TestPaymentGateway
from app.integrations.payment_gateway.factory import get_payment_gateway
from app.main import app
from app.modules.branches.models import Ciudad, Sucursal
from app.modules.catalog.models import Color, Producto, Talla, VarianteProducto
from app.modules.categories.models import Categoria
from app.modules.inventory.models import Inventario, MovimientoInventario
from app.modules.orders.models import Pedido
from app.modules.payments.models import Pago, Reembolso
from app.modules.returns.models import Devolucion
from app.modules.suppliers.models import Proveedor
from app.modules.users.models import Rol, Usuario


ROLE_NAMES = ("cliente", "administrador", "encargado", "cajero")


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with testing_session() as session:
        session.add_all(Rol(nombre=name) for name in ROLE_NAMES)
        session.commit()
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_payment_gateway] = TestPaymentGateway
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def commerce_context(db: Session) -> dict[str, object]:
    city = Ciudad(nombre="La Paz", departamento="La Paz")
    branch = Sucursal(
        ciudad=city,
        nombre="Centro",
        direccion="Av. Principal 100",
        horario_informativo="Lunes a sábado",
        activa=True,
    )
    other_branch = Sucursal(
        ciudad=city,
        nombre="Sur",
        direccion="Calle 20",
        horario_informativo="Lunes a viernes",
        activa=True,
    )
    category = Categoria(nombre="Poleras", activa=True)
    supplier = Proveedor(nombre="Textiles Bolivia", activo=True)
    product = Producto(
        categoria=category,
        proveedor=supplier,
        nombre="Polera básica",
        precio_base=Decimal("80.00"),
        activo=True,
    )
    variant = VarianteProducto(
        producto=product,
        talla=Talla(nombre="M", orden=2),
        color=Color(nombre="Negro", codigo_hex="#000000"),
        sku="POL-M-NEG",
        activa=True,
    )
    db.add_all([branch, other_branch, variant])
    db.commit()
    return {"branch": branch, "other_branch": other_branch, "variant": variant}


def auth_identity(
    client: TestClient,
    db: Session,
    role_name: str,
    *,
    suffix: str,
    branch: Sucursal | None = None,
) -> tuple[Usuario, dict[str, str]]:
    role = db.scalar(select(Rol).where(Rol.nombre == role_name))
    assert role is not None
    user = Usuario(
        email=f"payments-{role_name}-{suffix}@example.com",
        password_hash=hash_password("ClaveSegura123"),
        nombres="Usuario",
        apellidos=role_name.title(),
        activo=True,
        sucursal=branch,
        roles=[role],
    )
    db.add(user)
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "ClaveSegura123"},
    )
    assert response.status_code == 200
    return user, {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_web_order(
    client: TestClient,
    db: Session,
    context: dict[str, object],
    *,
    suffix: str,
    quantity: int = 3,
) -> tuple[dict, Usuario, dict[str, str], dict[str, str]]:
    branch = context["branch"]
    variant = context["variant"]
    assert isinstance(branch, Sucursal) and isinstance(variant, VarianteProducto)
    _, admin_headers = auth_identity(client, db, "administrador", suffix=suffix)
    customer, customer_headers = auth_identity(client, db, "cliente", suffix=suffix)
    receipt = client.post(
        "/api/v1/inventory/receipts",
        headers=admin_headers,
        json={
            "sucursal_id": str(branch.id),
            "variante_id": str(variant.id),
            "cantidad": 10,
        },
    )
    assert receipt.status_code == 201, receipt.text
    assert client.post(
        "/api/v1/cart/items",
        headers=customer_headers,
        json={"variante_id": str(variant.id), "cantidad": quantity},
    ).status_code == 201
    checkout = client.post(
        "/api/v1/orders/checkout",
        headers=customer_headers,
        json={"sucursal_id": str(branch.id)},
    )
    assert checkout.status_code == 201, checkout.text
    return checkout.json(), customer, customer_headers, admin_headers


def pay_order(
    client: TestClient, order: dict, headers: dict[str, str]
) -> dict:
    initiated = client.post(
        f"/api/v1/payments/orders/{order['id']}", headers=headers
    )
    assert initiated.status_code == 201, initiated.text
    confirmed = client.post(
        f"/api/v1/payments/{initiated.json()['id']}/confirm",
        headers=headers,
        json={"resultado_prueba": "APROBAR"},
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


def transition_return(
    client: TestClient,
    return_id: str,
    headers: dict[str, str],
    state: str,
) -> dict:
    response = client.patch(
        f"/api/v1/returns/manage/{return_id}/status",
        headers=headers,
        json={
            "estado": state,
            "reingresar_stock": True,
            "generar_reembolso": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_test_gateway_approves_backend_amount_and_prevents_duplicate_attempts(
    client: TestClient, db: Session, commerce_context: dict[str, object]
) -> None:
    order, _, customer_headers, _ = create_web_order(
        client, db, commerce_context, suffix="approve", quantity=2
    )
    empty = client.get(
        f"/api/v1/payments/orders/{order['id']}", headers=customer_headers
    )
    assert empty.status_code == 200 and empty.json() is None

    initiated = client.post(
        f"/api/v1/payments/orders/{order['id']}", headers=customer_headers
    )
    assert initiated.status_code == 201, initiated.text
    payment = initiated.json()
    assert payment["estado"] == "PENDIENTE"
    assert payment["monto"] == "160.00"
    assert payment["ambiente"] == "PRUEBA"
    assert payment["referencia_externa"].startswith("TEST-PAY-")

    confirmed = client.post(
        f"/api/v1/payments/{payment['id']}/confirm",
        headers=customer_headers,
        json={"resultado_prueba": "APROBAR"},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["estado"] == "APROBADO"
    assert confirmed.json()["pagado_en"] is not None
    db.expire_all()
    assert db.get(Pedido, UUID(order["id"])).estado == "PAGADO"  # type: ignore[union-attr]
    assert client.post(
        f"/api/v1/payments/orders/{order['id']}", headers=customer_headers
    ).status_code == 409
    assert client.post(
        f"/api/v1/payments/{payment['id']}/confirm",
        headers=customer_headers,
        json={"resultado_prueba": "APROBAR"},
    ).status_code == 409


def test_rejected_payment_cancels_order_and_restores_inventory(
    client: TestClient, db: Session, commerce_context: dict[str, object]
) -> None:
    order, _, customer_headers, _ = create_web_order(
        client, db, commerce_context, suffix="reject", quantity=2
    )
    initiated = client.post(
        f"/api/v1/payments/orders/{order['id']}", headers=customer_headers
    ).json()
    rejected = client.post(
        f"/api/v1/payments/{initiated['id']}/confirm",
        headers=customer_headers,
        json={"resultado_prueba": "RECHAZAR"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["estado"] == "RECHAZADO"
    db.expire_all()
    assert db.get(Pedido, UUID(order["id"])).estado == "CANCELADO"  # type: ignore[union-attr]
    stock = db.scalar(select(Inventario))
    assert stock is not None and stock.stock_fisico == 10
    restoration = list(
        db.scalars(
                select(MovimientoInventario).where(
                    MovimientoInventario.tipo == "DEVOLUCION",
                    MovimientoInventario.referencia_id == UUID(initiated["id"]),
                )
        )
    )
    assert len(restoration) == 1 and restoration[0].cantidad == 2
    assert restoration[0].referencia_tipo == "PAGO"


def test_partial_returns_refund_historical_amount_and_never_exceed_purchase(
    client: TestClient, db: Session, commerce_context: dict[str, object]
) -> None:
    order, _, customer_headers, _ = create_web_order(
        client, db, commerce_context, suffix="returns", quantity=3
    )
    payment = pay_order(client, order, customer_headers)
    branch = commerce_context["branch"]
    assert isinstance(branch, Sucursal)
    _, manager_headers = auth_identity(
        client, db, "encargado", suffix="returns", branch=branch
    )
    order_detail_id = order["detalles"][0]["id"]

    first = client.post(
        "/api/v1/returns",
        headers=customer_headers,
        json={
            "pedido_id": order["id"],
            "motivo_general": "Talla incorrecta",
            "detalles": [
                {
                    "detalle_pedido_id": order_detail_id,
                    "cantidad": 1,
                    "motivo": "Muy grande",
                }
            ],
        },
    )
    assert first.status_code == 201, first.text
    assert first.json()["monto_estimado"] == "80.00"
    over_return = client.post(
        "/api/v1/returns",
        headers=customer_headers,
        json={
            "pedido_id": order["id"],
            "detalles": [{"detalle_pedido_id": order_detail_id, "cantidad": 3}],
        },
    )
    assert over_return.status_code == 409

    transition_return(client, first.json()["id"], manager_headers, "APROBADA")
    completed = transition_return(
        client, first.json()["id"], manager_headers, "COMPLETADA"
    )
    assert completed["reingresa_stock"] is True
    assert completed["reembolso"]["monto"] == "80.00"
    assert completed["reembolso"]["estado"] == "COMPLETADO"
    assert completed["reembolso"]["referencia_externa"].startswith("TEST-REF-")
    db.expire_all()
    assert db.scalar(select(Inventario)).stock_fisico == 8  # type: ignore[union-attr]
    assert db.get(Pago, UUID(payment["id"])).estado == "APROBADO"  # type: ignore[union-attr]

    second = client.post(
        "/api/v1/returns",
        headers=customer_headers,
        json={
            "pedido_id": order["id"],
            "motivo_general": "Resto del pedido",
            "detalles": [{"detalle_pedido_id": order_detail_id, "cantidad": 2}],
        },
    )
    assert second.status_code == 201, second.text
    transition_return(client, second.json()["id"], manager_headers, "APROBADA")
    transition_return(client, second.json()["id"], manager_headers, "COMPLETADA")
    db.expire_all()
    assert db.scalar(select(Inventario)).stock_fisico == 10  # type: ignore[union-attr]
    assert db.get(Pago, UUID(payment["id"])).estado == "REEMBOLSADO"  # type: ignore[union-attr]
    assert db.get(Pedido, UUID(order["id"])).estado == "REEMBOLSADO"  # type: ignore[union-attr]
    assert sum(item.monto for item in db.scalars(select(Reembolso))) == Decimal("240.00")


def test_return_permissions_customer_cancel_and_pos_cash_payment(
    client: TestClient, db: Session, commerce_context: dict[str, object]
) -> None:
    order, _, customer_headers, admin_headers = create_web_order(
        client, db, commerce_context, suffix="permissions", quantity=1
    )
    pay_order(client, order, customer_headers)
    _, other_headers = auth_identity(
        client, db, "cliente", suffix="permissions-other"
    )
    detail_id = order["detalles"][0]["id"]
    payload = {
        "pedido_id": order["id"],
        "detalles": [{"detalle_pedido_id": detail_id, "cantidad": 1}],
    }
    assert client.post(
        "/api/v1/returns", headers=other_headers, json=payload
    ).status_code == 404
    created = client.post(
        "/api/v1/returns", headers=customer_headers, json=payload
    )
    assert created.status_code == 201, created.text
    cancelled = client.post(
        f"/api/v1/returns/{created.json()['id']}/cancel",
        headers=customer_headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["estado"] == "CANCELADA"

    branch = commerce_context["branch"]
    other_branch = commerce_context["other_branch"]
    variant = commerce_context["variant"]
    assert isinstance(branch, Sucursal) and isinstance(other_branch, Sucursal)
    assert isinstance(variant, VarianteProducto)
    _, cashier_headers = auth_identity(
        client, db, "cajero", suffix="permissions", branch=branch
    )
    pos = client.post(
        "/api/v1/orders/pos",
        headers=cashier_headers,
        json={
            "sucursal_id": str(branch.id),
            "detalles": [{"variante_id": str(variant.id), "cantidad": 1}],
        },
    )
    assert pos.status_code == 201, pos.text
    db.expire_all()
    cash_payment = db.scalar(
        select(Pago).where(Pago.pedido_id == UUID(pos.json()["id"]))
    )
    assert cash_payment is not None
    assert cash_payment.metodo == "CAJA" and cash_payment.estado == "APROBADO"

    _, other_manager_headers = auth_identity(
        client, db, "encargado", suffix="permissions-other", branch=other_branch
    )
    assert client.get(
        "/api/v1/returns/manage",
        headers=other_manager_headers,
        params={"branch_id": str(branch.id)},
    ).status_code == 403
    assert client.get("/api/v1/returns/manage", headers=admin_headers).status_code == 200
