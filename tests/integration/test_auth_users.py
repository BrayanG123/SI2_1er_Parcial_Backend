from collections.abc import Generator
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
from app.modules.users.models import PerfilCliente, Rol, Usuario


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
        session.add_all(
            [Rol(nombre=name, descripcion=f"Rol {name}") for name in ROLE_NAMES]
        )
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


def register_client(client: TestClient, email: str = "cliente@example.com") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "ClaveSegura123",
            "nombres": "Ana",
            "apellidos": "Pérez",
            "telefono": "70000000",
            "direccion": "Calle Principal 123",
        },
    )
    assert response.status_code == 201
    return response.json()


def login(client: TestClient, email: str, password: str = "ClaveSegura123") -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def create_admin(db: Session) -> Usuario:
    role = db.scalar(select(Rol).where(Rol.nombre == "administrador"))
    assert role is not None
    admin = Usuario(
        email="admin@example.com",
        password_hash=hash_password("AdminSegura123"),
        nombres="Ada",
        apellidos="Admin",
        activo=True,
        roles=[role],
        perfil_cliente=PerfilCliente(),
    )
    db.add(admin)
    db.commit()
    return admin


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_login_and_current_user_never_expose_password_hash(
    client: TestClient,
    db: Session,
) -> None:
    registered = register_client(client)

    assert registered["email"] == "cliente@example.com"
    assert registered["roles"][0]["nombre"] == "cliente"
    assert "password" not in registered
    assert "password_hash" not in registered

    stored_user = db.scalar(select(Usuario).where(Usuario.email == "cliente@example.com"))
    assert stored_user is not None
    assert stored_user.password_hash != "ClaveSegura123"
    assert stored_user.password_hash.startswith("$argon2")

    authenticated = login(client, "cliente@example.com")
    response = client.get(
        "/api/v1/auth/me",
        headers=bearer(authenticated["access_token"]),
    )

    assert response.status_code == 200
    assert response.json()["id"] == registered["id"]
    assert "password_hash" not in response.json()


def test_duplicate_email_is_rejected(client: TestClient) -> None:
    register_client(client, "DUPLICATE@example.com")

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "OtraClave123",
            "nombres": "Otra",
            "apellidos": "Persona",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_invalid_token_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers=bearer("token-invalido"),
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_inactive_user_cannot_login(client: TestClient, db: Session) -> None:
    registered = register_client(client, "inactivo@example.com")
    user = db.get(Usuario, UUID(registered["id"]))
    assert user is not None
    user.activo = False
    db.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "inactivo@example.com", "password": "ClaveSegura123"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "La cuenta está desactivada."


def test_client_role_cannot_access_user_administration(client: TestClient) -> None:
    register_client(client)
    token = login(client, "cliente@example.com")["access_token"]

    response = client.get("/api/v1/users", headers=bearer(token))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_admin_can_manage_users_and_custom_roles(client: TestClient, db: Session) -> None:
    create_admin(db)
    token = login(client, "admin@example.com", "AdminSegura123")["access_token"]
    headers = bearer(token)

    role_response = client.post(
        "/api/v1/roles",
        headers=headers,
        json={"nombre": "auditor", "descripcion": "Consulta información"},
    )
    assert role_response.status_code == 201

    create_response = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "auditor@example.com",
            "password": "AuditorSeguro123",
            "nombres": "Alex",
            "apellidos": "Auditor",
            "roles": ["auditor"],
        },
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"activo": False, "roles": ["cliente", "auditor"]},
    )
    assert update_response.status_code == 200
    assert update_response.json()["activo"] is False
    assert {role["nombre"] for role in update_response.json()["roles"]} == {
        "cliente",
        "auditor",
    }

    list_response = client.get("/api/v1/users", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 2


def test_protected_roles_cannot_be_deleted(client: TestClient, db: Session) -> None:
    create_admin(db)
    token = login(client, "admin@example.com", "AdminSegura123")["access_token"]
    client_role = db.scalar(select(Rol).where(Rol.nombre == "cliente"))
    assert client_role is not None

    response = client.delete(
        f"/api/v1/roles/{client_role.id}",
        headers=bearer(token),
    )

    assert response.status_code == 409
