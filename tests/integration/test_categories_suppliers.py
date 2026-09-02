from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.modules.users.models import Rol, Usuario


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
        session.add_all(Rol(nombre=name) for name in ("cliente", "administrador"))
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


def auth_headers(client: TestClient, db: Session, role_name: str) -> dict[str, str]:
    role = db.scalar(select(Rol).where(Rol.nombre == role_name))
    assert role is not None
    email = f"{role_name}@example.com"
    db.add(
        Usuario(
            email=email,
            password_hash=hash_password("ClaveSegura123"),
            nombres="Usuario",
            apellidos="Prueba",
            activo=True,
            roles=[role],
        )
    )
    db.commit()
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "ClaveSegura123"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_non_admin_cannot_access_master_data(client: TestClient, db: Session) -> None:
    headers = auth_headers(client, db, "cliente")
    assert client.get("/api/v1/categories", headers=headers).status_code == 403
    assert client.get("/api/v1/suppliers", headers=headers).status_code == 403


def test_admin_can_manage_categories(client: TestClient, db: Session) -> None:
    headers = auth_headers(client, db, "administrador")
    created = client.post(
        "/api/v1/categories",
        headers=headers,
        json={"nombre": "Vestidos", "descripcion": "Vestidos casuales"},
    )
    assert created.status_code == 201
    category_id = created.json()["id"]

    duplicate = client.post(
        "/api/v1/categories", headers=headers, json={"nombre": "vestidos"}
    )
    updated = client.patch(
        f"/api/v1/categories/{category_id}", headers=headers, json={"activa": False}
    )
    listed = client.get("/api/v1/categories?q=vest", headers=headers)

    assert duplicate.status_code == 409
    assert updated.status_code == 200 and updated.json()["activa"] is False
    assert listed.status_code == 200 and listed.json()["total"] == 1


def test_admin_can_manage_suppliers_and_nit_is_unique(client: TestClient, db: Session) -> None:
    headers = auth_headers(client, db, "administrador")
    created = client.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "nombre": "Textiles Andinos",
            "nit": "1020304050",
            "telefono": "70000000",
            "email": "VENTAS@ANDINOS.COM",
            "direccion": "Parque industrial",
        },
    )
    assert created.status_code == 201
    assert created.json()["email"] == "ventas@andinos.com"

    duplicate = client.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"nombre": "Otro proveedor", "nit": "1020304050"},
    )
    updated = client.patch(
        f"/api/v1/suppliers/{created.json()['id']}",
        headers=headers,
        json={"activo": False, "telefono": None},
    )
    listed = client.get("/api/v1/suppliers?q=andinos", headers=headers)

    assert duplicate.status_code == 409
    assert updated.status_code == 200 and updated.json()["activo"] is False
    assert updated.json()["telefono"] is None
    assert listed.status_code == 200 and listed.json()["total"] == 1
