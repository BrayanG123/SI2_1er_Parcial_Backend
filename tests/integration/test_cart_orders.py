from collections.abc import Generator
from datetime import date, timedelta
from decimal import Decimal

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
from app.modules.cart.models import Carrito
from app.modules.catalog.models import Color, Producto, Talla, VarianteProducto
from app.modules.categories.models import Categoria
from app.modules.inventory.models import Inventario, MovimientoInventario
from app.modules.orders.models import Pedido
from app.modules.reservations.models import Reserva
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
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
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
def sales_context(db: Session) -> dict[str, object]:
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
    size_m = Talla(nombre="M", orden=2)
    size_l = Talla(nombre="L", orden=3)
    black = Color(nombre="Negro", codigo_hex="#000000")
    white = Color(nombre="Blanco", codigo_hex="#ffffff")
    product = Producto(
        categoria=category,
        proveedor=supplier,
        nombre="Polera básica",
        marca="Andina",
        precio_base=Decimal("80.00"),
        activo=True,
    )
    variant_m = VarianteProducto(
        producto=product, talla=size_m, color=black, sku="POL-M-NEG", activa=True
    )
    variant_l = VarianteProducto(
        producto=product,
        talla=size_l,
        color=white,
        sku="POL-L-BLA",
        precio=Decimal("95.00"),
        activa=True,
    )
    db.add_all([branch, other_branch, variant_m, variant_l])
    db.commit()
    return {
        "branch": branch,
        "other_branch": other_branch,
        "product": product,
        "variants": [variant_m, variant_l],
    }


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
        email=f"orders-{role_name}-{suffix}@example.com",
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


def load_stock(
    client: TestClient,
    admin_headers: dict[str, str],
    branch: Sucursal,
    variants: list[VarianteProducto],
    quantity: int = 10,
) -> None:
    for variant in variants:
        response = client.post(
            "/api/v1/inventory/receipts",
            headers=admin_headers,
            json={
                "sucursal_id": str(branch.id),
                "variante_id": str(variant.id),
                "cantidad": quantity,
            },
        )
        assert response.status_code == 201, response.text


def add_to_cart(
    client: TestClient,
    headers: dict[str, str],
    variant: VarianteProducto,
    quantity: int,
) -> dict:
    response = client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={"variante_id": str(variant.id), "cantidad": quantity},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_customer_edits_and_clears_one_active_cart(
    client: TestClient, db: Session, sales_context: dict[str, object]
) -> None:
    variants = sales_context["variants"]
    assert isinstance(variants, list)
    _, customer_headers = auth_identity(client, db, "cliente", suffix="cart")

    cart = add_to_cart(client, customer_headers, variants[0], 1)
    cart = add_to_cart(client, customer_headers, variants[0], 2)
    assert len(cart["detalles"]) == 1
    assert cart["detalles"][0]["cantidad"] == 3
    assert cart["subtotal_estimado"] == "240.00"

    item_id = cart["detalles"][0]["id"]
    updated = client.patch(
        f"/api/v1/cart/items/{item_id}",
        headers=customer_headers,
        json={"cantidad": 2},
    )
    assert updated.status_code == 200
    assert updated.json()["detalles"][0]["cantidad"] == 2
    removed = client.delete(f"/api/v1/cart/items/{item_id}", headers=customer_headers)
    assert removed.status_code == 200 and removed.json()["detalles"] == []
    assert client.delete("/api/v1/cart", headers=customer_headers).status_code == 204
    assert db.scalar(select(Carrito).where(Carrito.activo.is_(True))) is not None


def test_web_checkout_recalculates_prices_and_updates_inventory_atomically(
    client: TestClient, db: Session, sales_context: dict[str, object]
) -> None:
    branch = sales_context["branch"]
    product = sales_context["product"]
    variants = sales_context["variants"]
    assert isinstance(branch, Sucursal) and isinstance(product, Producto)
    assert isinstance(variants, list)
    _, admin_headers = auth_identity(client, db, "administrador", suffix="web")
    customer, customer_headers = auth_identity(client, db, "cliente", suffix="web")
    load_stock(client, admin_headers, branch, variants)
    add_to_cart(client, customer_headers, variants[0], 2)
    add_to_cart(client, customer_headers, variants[1], 1)

    product.precio_base = Decimal("85.00")
    db.commit()
    checkout = client.post(
        "/api/v1/orders/checkout",
        headers=customer_headers,
        json={"sucursal_id": str(branch.id), "canal": "WEB"},
    )
    assert checkout.status_code == 201, checkout.text
    order = checkout.json()
    assert order["canal"] == "WEB" and order["estado"] == "CREADO"
    assert order["cliente_id"] == str(customer.id)
    assert order["subtotal"] == "265.00"
    assert order["descuento"] == "0.00" and order["total"] == "265.00"
    assert order["numero"].startswith("PED-")

    db.expire_all()
    stocks = list(db.scalars(select(Inventario)))
    assert sum(item.stock_fisico for item in stocks) == 17
    assert sum(item.stock_reservado for item in stocks) == 0
    sales = list(db.scalars(select(MovimientoInventario).where(MovimientoInventario.tipo == "VENTA")))
    assert sum(item.cantidad for item in sales) == -3

    product.precio_base = Decimal("120.00")
    db.commit()
    detail = client.get(f"/api/v1/orders/mine/{order['id']}", headers=customer_headers)
    assert detail.status_code == 200
    assert detail.json()["total"] == "265.00"
    assert client.get("/api/v1/cart", headers=customer_headers).json()["detalles"] == []


def test_stock_failure_rolls_back_order_inventory_and_cart(
    client: TestClient, db: Session, sales_context: dict[str, object]
) -> None:
    branch = sales_context["branch"]
    variants = sales_context["variants"]
    assert isinstance(branch, Sucursal) and isinstance(variants, list)
    _, admin_headers = auth_identity(client, db, "administrador", suffix="rollback")
    _, customer_headers = auth_identity(client, db, "cliente", suffix="rollback")
    load_stock(client, admin_headers, branch, variants, quantity=2)
    add_to_cart(client, customer_headers, variants[0], 3)

    checkout = client.post(
        "/api/v1/orders/checkout",
        headers=customer_headers,
        json={"sucursal_id": str(branch.id)},
    )
    assert checkout.status_code == 409
    assert db.scalar(select(Pedido)) is None
    db.expire_all()
    assert sum(item.stock_fisico for item in db.scalars(select(Inventario))) == 4
    assert client.get("/api/v1/cart", headers=customer_headers).json()["detalles"][0]["cantidad"] == 3


def test_customer_buys_part_of_reservation_and_releases_the_rest(
    client: TestClient, db: Session, sales_context: dict[str, object]
) -> None:
    branch = sales_context["branch"]
    product = sales_context["product"]
    variants = sales_context["variants"]
    assert isinstance(branch, Sucursal) and isinstance(product, Producto)
    assert isinstance(variants, list)
    _, admin_headers = auth_identity(client, db, "administrador", suffix="reserved")
    _, customer_headers = auth_identity(client, db, "cliente", suffix="reserved")
    load_stock(client, admin_headers, branch, variants)
    reservation = client.post(
        "/api/v1/reservations",
        headers=customer_headers,
        json={
            "sucursal_id": str(branch.id),
            "fecha_visita": str(date.today() + timedelta(days=1)),
            "detalles": [
                {"variante_id": str(variants[0].id), "cantidad": 3},
                {"variante_id": str(variants[1].id), "cantidad": 2},
            ],
        },
    )
    assert reservation.status_code == 201, reservation.text

    product.precio_base = Decimal("90.00")
    db.commit()

    checkout = client.post(
        f"/api/v1/orders/from-reservation/{reservation.json()['id']}",
        headers=customer_headers,
        json={
            "canal": "WEB",
            "detalles": [{"variante_id": str(variants[0].id), "cantidad": 2}],
        },
    )
    assert checkout.status_code == 201, checkout.text
    assert checkout.json()["reserva_id"] == reservation.json()["id"]
    assert checkout.json()["total"] == "180.00"
    db.expire_all()
    stock_by_variant = {
        item.variante_id: item for item in db.scalars(select(Inventario))
    }
    assert stock_by_variant[variants[0].id].stock_fisico == 8
    assert stock_by_variant[variants[0].id].stock_reservado == 0
    assert stock_by_variant[variants[1].id].stock_fisico == 10
    assert stock_by_variant[variants[1].id].stock_reservado == 0
    assert db.scalar(select(Reserva)).estado == "COMPLETADA"  # type: ignore[union-attr]
    assert client.post(
        f"/api/v1/orders/from-reservation/{reservation.json()['id']}",
        headers=customer_headers,
        json={"detalles": [{"variante_id": str(variants[0].id), "cantidad": 1}]},
    ).status_code == 409


def test_pos_search_sale_optional_customer_and_branch_permissions(
    client: TestClient, db: Session, sales_context: dict[str, object]
) -> None:
    branch = sales_context["branch"]
    other_branch = sales_context["other_branch"]
    variants = sales_context["variants"]
    assert isinstance(branch, Sucursal) and isinstance(other_branch, Sucursal)
    assert isinstance(variants, list)
    _, admin_headers = auth_identity(client, db, "administrador", suffix="pos")
    customer, _ = auth_identity(client, db, "cliente", suffix="pos")
    _, cashier_headers = auth_identity(client, db, "cajero", suffix="pos", branch=branch)
    _, manager_headers = auth_identity(client, db, "encargado", suffix="pos", branch=branch)
    load_stock(client, admin_headers, branch, variants)

    search = client.get(
        "/api/v1/orders/pos/variants", headers=cashier_headers, params={"sku": "POL-M"}
    )
    assert search.status_code == 200 and len(search.json()) == 1
    assert search.json()[0]["stock_disponible"] == 10
    assert client.get(
        "/api/v1/orders/pos/variants",
        headers=cashier_headers,
        params={"sku": "POL", "branch_id": str(other_branch.id)},
    ).status_code == 403

    sale = client.post(
        "/api/v1/orders/pos",
        headers=cashier_headers,
        json={
            "sucursal_id": str(branch.id),
            "cliente_id": str(customer.id),
            "detalles": [{"variante_id": str(variants[1].id), "cantidad": 2}],
        },
    )
    assert sale.status_code == 201, sale.text
    assert sale.json()["canal"] == "POS" and sale.json()["estado"] == "COMPLETADO"
    assert sale.json()["total"] == "190.00"
    assert sale.json()["cliente"]["id"] == str(customer.id)

    anonymous_sale = client.post(
        "/api/v1/orders/pos",
        headers=cashier_headers,
        json={
            "sucursal_id": str(branch.id),
            "detalles": [{"variante_id": str(variants[0].id), "cantidad": 1}],
        },
    )
    assert anonymous_sale.status_code == 201, anonymous_sale.text
    assert anonymous_sale.json()["cliente_id"] is None
    assert anonymous_sale.json()["cliente"] is None

    assert client.post(
        "/api/v1/orders/pos",
        headers=manager_headers,
        json={
            "sucursal_id": str(branch.id),
            "detalles": [{"variante_id": str(variants[0].id), "cantidad": 1}],
        },
    ).status_code == 403


def test_customer_and_staff_order_history_respects_ownership_and_branch(
    client: TestClient, db: Session, sales_context: dict[str, object]
) -> None:
    branch = sales_context["branch"]
    other_branch = sales_context["other_branch"]
    variants = sales_context["variants"]
    assert isinstance(branch, Sucursal) and isinstance(other_branch, Sucursal)
    assert isinstance(variants, list)
    _, admin_headers = auth_identity(client, db, "administrador", suffix="history")
    _, customer_headers = auth_identity(client, db, "cliente", suffix="history")
    _, other_headers = auth_identity(client, db, "cliente", suffix="history-other")
    _, cashier_headers = auth_identity(client, db, "cajero", suffix="history", branch=branch)
    load_stock(client, admin_headers, branch, variants)
    add_to_cart(client, customer_headers, variants[0], 1)
    order = client.post(
        "/api/v1/orders/checkout",
        headers=customer_headers,
        json={"sucursal_id": str(branch.id)},
    ).json()

    mine = client.get("/api/v1/orders/mine", headers=customer_headers)
    assert mine.status_code == 200 and mine.json()["total"] == 1
    assert client.get(f"/api/v1/orders/mine/{order['id']}", headers=other_headers).status_code == 404
    managed = client.get(
        "/api/v1/orders/manage",
        headers=cashier_headers,
        params={"channel": "WEB", "state": "CREADO"},
    )
    assert managed.status_code == 200 and managed.json()["total"] == 1
    assert client.get(
        "/api/v1/orders/manage",
        headers=cashier_headers,
        params={"branch_id": str(other_branch.id)},
    ).status_code == 403
