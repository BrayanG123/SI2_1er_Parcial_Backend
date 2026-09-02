from collections.abc import Generator
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.exceptions import ConflictError
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.modules.branches.models import Ciudad, Sucursal
from app.modules.catalog.models import Color, Producto, Talla, VarianteProducto
from app.modules.categories.models import Categoria
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.service import InventoryService
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
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def stock_context(db: Session) -> dict[str, object]:
    city = Ciudad(nombre="La Paz", departamento="La Paz")
    branch = Sucursal(
        ciudad=city,
        nombre="Centro",
        direccion="Av. Principal 100",
        horario_informativo="Lunes a sabado",
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
    size = Talla(nombre="M", orden=2)
    color = Color(nombre="Negro", codigo_hex="#000000")
    product = Producto(
        categoria=category,
        proveedor=supplier,
        nombre="Polera basica",
        marca="Andina",
        precio_base=Decimal("80.00"),
        activo=True,
    )
    variant = VarianteProducto(
        producto=product,
        talla=size,
        color=color,
        sku="POL-M-NEG",
        activa=True,
    )
    db.add_all([branch, other_branch, variant])
    db.commit()
    return {
        "branch": branch,
        "other_branch": other_branch,
        "product": product,
        "variant": variant,
    }


def auth_headers(
    client: TestClient,
    db: Session,
    role_name: str,
    *,
    branch: Sucursal | None = None,
) -> dict[str, str]:
    role = db.scalar(select(Rol).where(Rol.nombre == role_name))
    assert role is not None
    scope = branch.nombre.lower() if branch else "global"
    email = f"inventory-{role_name}-{scope}@example.com"
    user = Usuario(
        email=email,
        password_hash=hash_password("ClaveSegura123"),
        nombres="Usuario",
        apellidos="Inventario",
        activo=True,
        sucursal=branch,
        roles=[role],
    )
    db.add(user)
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "ClaveSegura123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_receipt_adjustment_history_and_public_availability(
    client: TestClient, db: Session, stock_context: dict[str, object]
) -> None:
    headers = auth_headers(client, db, "administrador")
    branch = stock_context["branch"]
    variant = stock_context["variant"]
    product = stock_context["product"]
    assert isinstance(branch, Sucursal)
    assert isinstance(variant, VarianteProducto)
    assert isinstance(product, Producto)

    receipt = client.post(
        "/api/v1/inventory/receipts",
        headers=headers,
        json={
            "sucursal_id": str(branch.id),
            "variante_id": str(variant.id),
            "cantidad": 10,
            "observacion": "Ingreso de proveedor",
        },
    )
    assert receipt.status_code == 201, receipt.text
    assert receipt.json()["stock_fisico"] == 10
    assert receipt.json()["stock_disponible"] == 10

    adjustment = client.post(
        "/api/v1/inventory/adjustments",
        headers=headers,
        json={
            "sucursal_id": str(branch.id),
            "variante_id": str(variant.id),
            "cantidad": -3,
            "motivo": "Conteo fisico",
        },
    )
    assert adjustment.status_code == 200, adjustment.text
    inventory = adjustment.json()
    assert inventory["stock_fisico"] == 7
    assert inventory["stock_disponible"] == 7

    listing = client.get(
        "/api/v1/inventory", headers=headers, params={"state": "DISPONIBLE"}
    )
    history = client.get(
        f"/api/v1/inventory/{inventory['id']}/movements", headers=headers
    )
    availability = client.get(f"/api/v1/catalog/products/{product.id}/availability")
    assert listing.status_code == 200 and listing.json()["total"] == 1
    assert history.status_code == 200 and history.json()["total"] == 2
    assert {row["tipo"] for row in history.json()["items"]} == {"RECEPCION", "AJUSTE"}
    assert availability.status_code == 200
    assert availability.json()[0]["stock_disponible"] == 7

    invalid = client.post(
        "/api/v1/inventory/adjustments",
        headers=headers,
        json={
            "sucursal_id": str(branch.id),
            "variante_id": str(variant.id),
            "cantidad": -8,
            "motivo": "Ajuste imposible",
        },
    )
    assert invalid.status_code == 409


def test_branch_scope_and_inventory_roles(
    client: TestClient, db: Session, stock_context: dict[str, object]
) -> None:
    branch = stock_context["branch"]
    other_branch = stock_context["other_branch"]
    variant = stock_context["variant"]
    assert isinstance(branch, Sucursal)
    assert isinstance(other_branch, Sucursal)
    assert isinstance(variant, VarianteProducto)
    manager_headers = auth_headers(client, db, "encargado", branch=branch)
    cashier_headers = auth_headers(client, db, "cajero", branch=branch)
    client_headers = auth_headers(client, db, "cliente")

    own_receipt = client.post(
        "/api/v1/inventory/receipts",
        headers=manager_headers,
        json={"sucursal_id": str(branch.id), "variante_id": str(variant.id), "cantidad": 5},
    )
    other_receipt = client.post(
        "/api/v1/inventory/receipts",
        headers=manager_headers,
        json={
            "sucursal_id": str(other_branch.id),
            "variante_id": str(variant.id),
            "cantidad": 5,
        },
    )
    cashier_list = client.get("/api/v1/inventory", headers=cashier_headers)
    cashier_write = client.post(
        "/api/v1/inventory/adjustments",
        headers=cashier_headers,
        json={
            "sucursal_id": str(branch.id),
            "variante_id": str(variant.id),
            "cantidad": 1,
            "motivo": "Conteo",
        },
    )
    assert own_receipt.status_code == 201
    assert other_receipt.status_code == 403
    assert cashier_list.status_code == 200 and cashier_list.json()["total"] == 1
    assert cashier_write.status_code == 403
    assert client.get("/api/v1/inventory", headers=client_headers).status_code == 403


def test_reservation_and_sale_never_consume_unavailable_stock(
    client: TestClient, db: Session, stock_context: dict[str, object]
) -> None:
    headers = auth_headers(client, db, "administrador")
    branch = stock_context["branch"]
    variant = stock_context["variant"]
    assert isinstance(branch, Sucursal)
    assert isinstance(variant, VarianteProducto)
    response = client.post(
        "/api/v1/inventory/receipts",
        headers=headers,
        json={"sucursal_id": str(branch.id), "variante_id": str(variant.id), "cantidad": 7},
    )
    assert response.status_code == 201

    service = InventoryService(db)
    reserved = service.reserve(branch.id, variant.id, 6, commit=True)
    assert reserved.stock_fisico == 7
    assert reserved.stock_reservado == 6
    assert reserved.stock_disponible == 1
    with pytest.raises(ConflictError, match="insuficiente"):
        service.sell(branch.id, variant.id, 2, commit=True)
    db.rollback()

    sold = service.sell(branch.id, variant.id, 4, from_reservation=True, commit=True)
    assert sold.stock_fisico == 3
    assert sold.stock_reservado == 2
    released = service.release_reservation(branch.id, variant.id, 2, commit=True)
    assert released.stock_fisico == 3
    assert released.stock_reservado == 0
    assert released.stock_disponible == 3


def test_critical_mutations_request_a_postgresql_row_lock(db: Session) -> None:
    captured: list[object] = []

    def capture(statement):  # type: ignore[no-untyped-def]
        captured.append(statement)
        return None

    db.scalar = capture  # type: ignore[method-assign]
    InventoryRepository(db).get_by_branch_variant(uuid4(), uuid4(), for_update=True)
    compiled = str(captured[0].compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE OF inventarios" in compiled
