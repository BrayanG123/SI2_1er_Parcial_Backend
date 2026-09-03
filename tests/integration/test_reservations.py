from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
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
from app.main import app
from app.modules.branches.models import Ciudad, Sucursal
from app.modules.catalog.models import Color, Producto, Talla, VarianteProducto
from app.modules.categories.models import Categoria
from app.modules.inventory.models import Inventario, MovimientoInventario
from app.modules.reservations.models import EstadoReserva, Reserva
from app.modules.reservations.service import ReservationService
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
def reservation_context(db: Session) -> dict[str, object]:
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
        producto=product, talla=size_l, color=white, sku="POL-L-BLA", activa=True
    )
    db.add_all([branch, other_branch, variant_m, variant_l])
    db.commit()
    return {
        "branch": branch,
        "other_branch": other_branch,
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
        email=f"reservas-{role_name}-{suffix}@example.com",
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


def reservation_payload(
    branch: Sucursal, variants: list[VarianteProducto], *, first_quantity: int = 2
) -> dict[str, object]:
    return {
        "sucursal_id": str(branch.id),
        "fecha_visita": str(date.today() + timedelta(days=1)),
        "hora_aproximada": "16:30:00",
        "detalles": [
            {"variante_id": str(variants[0].id), "cantidad": first_quantity},
            {"variante_id": str(variants[1].id), "cantidad": 1},
        ],
    }


def test_customer_creates_lists_and_cancels_multi_item_reservation(
    client: TestClient, db: Session, reservation_context: dict[str, object]
) -> None:
    branch = reservation_context["branch"]
    variants = reservation_context["variants"]
    assert isinstance(branch, Sucursal) and isinstance(variants, list)
    admin, admin_headers = auth_identity(client, db, "administrador", suffix="create")
    customer, customer_headers = auth_identity(client, db, "cliente", suffix="create")
    load_stock(client, admin_headers, branch, variants)

    created = client.post(
        "/api/v1/reservations",
        headers=customer_headers,
        json=reservation_payload(branch, variants),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["estado"] == "PENDIENTE"
    assert len(body["detalles"]) == 2
    assert body["cliente_id"] == str(customer.id)
    assert client.get("/api/v1/reservations/mine", headers=customer_headers).json()["total"] == 1

    inventories = list(db.scalars(select(Inventario).order_by(Inventario.variante_id)))
    assert sum(item.stock_reservado for item in inventories) == 3
    movements = list(db.scalars(select(MovimientoInventario)))
    assert sum(item.cantidad for item in movements if item.tipo == "RESERVA") == 3

    cancelled = client.post(
        f"/api/v1/reservations/{body['id']}/cancel", headers=customer_headers
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["estado"] == "CANCELADA"
    assert cancelled.json()["cancelada_en"] is not None
    db.expire_all()
    assert all(item.stock_reservado == 0 for item in db.scalars(select(Inventario)))
    assert client.post(
        f"/api/v1/reservations/{body['id']}/cancel", headers=customer_headers
    ).status_code == 409


def test_insufficient_stock_rolls_back_the_whole_reservation(
    client: TestClient, db: Session, reservation_context: dict[str, object]
) -> None:
    branch = reservation_context["branch"]
    variants = reservation_context["variants"]
    assert isinstance(branch, Sucursal) and isinstance(variants, list)
    _, admin_headers = auth_identity(client, db, "administrador", suffix="rollback")
    _, customer_headers = auth_identity(client, db, "cliente", suffix="rollback")
    load_stock(client, admin_headers, branch, variants, quantity=2)

    response = client.post(
        "/api/v1/reservations",
        headers=customer_headers,
        json=reservation_payload(branch, variants, first_quantity=3),
    )
    assert response.status_code == 409
    assert db.scalar(select(Reserva)) is None
    db.expire_all()
    assert all(item.stock_reservado == 0 for item in db.scalars(select(Inventario)))


def test_manager_transitions_prepared_reservation_and_branch_scope(
    client: TestClient, db: Session, reservation_context: dict[str, object]
) -> None:
    branch = reservation_context["branch"]
    other_branch = reservation_context["other_branch"]
    variants = reservation_context["variants"]
    assert isinstance(branch, Sucursal) and isinstance(other_branch, Sucursal)
    assert isinstance(variants, list)
    _, admin_headers = auth_identity(client, db, "administrador", suffix="flow")
    _, customer_headers = auth_identity(client, db, "cliente", suffix="flow")
    _, manager_headers = auth_identity(
        client, db, "encargado", suffix="flow", branch=branch
    )
    load_stock(client, admin_headers, branch, variants)
    created = client.post(
        "/api/v1/reservations",
        headers=customer_headers,
        json=reservation_payload(branch, variants),
    ).json()

    inbox = client.get("/api/v1/reservations/branch", headers=manager_headers)
    assert inbox.status_code == 200 and inbox.json()["total"] == 1
    forbidden = client.get(
        "/api/v1/reservations/branch",
        headers=manager_headers,
        params={"branch_id": str(other_branch.id)},
    )
    assert forbidden.status_code == 403

    for target in ("CONFIRMADA", "PREPARADA"):
        changed = client.patch(
            f"/api/v1/reservations/branch/{created['id']}/status",
            headers=manager_headers,
            json={"estado": target},
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["estado"] == target

    cancelled = client.post(
        f"/api/v1/reservations/{created['id']}/cancel", headers=customer_headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["estado"] == "CANCELADA"

    second = client.post(
        "/api/v1/reservations",
        headers=customer_headers,
        json=reservation_payload(branch, variants),
    ).json()
    for target in ("CONFIRMADA", "PREPARADA", "COMPLETADA"):
        completed = client.patch(
            f"/api/v1/reservations/branch/{second['id']}/status",
            headers=manager_headers,
            json={"estado": target},
        )
        assert completed.status_code == 200, completed.text
    assert completed.json()["estado"] == "COMPLETADA"
    db.expire_all()
    assert all(item.stock_reservado == 0 for item in db.scalars(select(Inventario)))


def test_expiration_releases_stock_and_permissions_are_enforced(
    client: TestClient, db: Session, reservation_context: dict[str, object]
) -> None:
    branch = reservation_context["branch"]
    variants = reservation_context["variants"]
    assert isinstance(branch, Sucursal) and isinstance(variants, list)
    _, admin_headers = auth_identity(client, db, "administrador", suffix="expire")
    _, customer_headers = auth_identity(client, db, "cliente", suffix="expire")
    _, cashier_headers = auth_identity(client, db, "cajero", suffix="expire", branch=branch)
    load_stock(client, admin_headers, branch, variants)
    created = client.post(
        "/api/v1/reservations",
        headers=customer_headers,
        json=reservation_payload(branch, variants),
    )
    assert created.status_code == 201
    reservation = db.get(Reserva, UUID(created.json()["id"]))
    assert reservation is not None

    assert client.get("/api/v1/reservations/branch", headers=customer_headers).status_code == 403
    assert client.get("/api/v1/reservations/branch", headers=cashier_headers).status_code == 403
    assert client.post(
        f"/api/v1/reservations/{created.json()['id']}/cancel", headers=cashier_headers
    ).status_code == 403
    expired = ReservationService(db).expire_due(
        now=datetime.now(UTC) + timedelta(days=3)
    )
    assert expired == 1
    db.expire_all()
    assert db.get(Reserva, reservation.id).estado == EstadoReserva.VENCIDA.value  # type: ignore[union-attr]
    assert all(item.stock_reservado == 0 for item in db.scalars(select(Inventario)))


def test_invalid_dates_duplicates_and_state_jumps_are_rejected(
    client: TestClient, db: Session, reservation_context: dict[str, object]
) -> None:
    branch = reservation_context["branch"]
    variants = reservation_context["variants"]
    assert isinstance(branch, Sucursal) and isinstance(variants, list)
    _, admin_headers = auth_identity(client, db, "administrador", suffix="invalid")
    _, customer_headers = auth_identity(client, db, "cliente", suffix="invalid")
    _, manager_headers = auth_identity(
        client, db, "encargado", suffix="invalid", branch=branch
    )
    load_stock(client, admin_headers, branch, variants)

    duplicate = reservation_payload(branch, variants)
    duplicate["detalles"] = [
        {"variante_id": str(variants[0].id), "cantidad": 1},
        {"variante_id": str(variants[0].id), "cantidad": 1},
    ]
    assert client.post(
        "/api/v1/reservations", headers=customer_headers, json=duplicate
    ).status_code == 422

    past = reservation_payload(branch, variants)
    past["fecha_visita"] = str(date.today() - timedelta(days=1))
    assert client.post(
        "/api/v1/reservations", headers=customer_headers, json=past
    ).status_code == 409

    created = client.post(
        "/api/v1/reservations",
        headers=customer_headers,
        json=reservation_payload(branch, variants),
    ).json()
    invalid_jump = client.patch(
        f"/api/v1/reservations/branch/{created['id']}/status",
        headers=manager_headers,
        json={"estado": "PREPARADA"},
    )
    assert invalid_jump.status_code == 409
