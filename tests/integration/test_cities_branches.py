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
        session.add_all(
            Rol(nombre=name, descripcion=name)
            for name in ("cliente", "administrador", "encargado", "cajero")
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


def create_user(db: Session, role_name: str, email: str) -> Usuario:
    role = db.scalar(select(Rol).where(Rol.nombre == role_name))
    assert role is not None
    user = Usuario(
        email=email,
        password_hash=hash_password("ClaveSegura123"),
        nombres="Usuario",
        apellidos="Prueba",
        activo=True,
        roles=[role],
    )
    db.add(user)
    db.commit()
    return user


def headers_for(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "ClaveSegura123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_city(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/v1/cities",
        headers=headers,
        json={"nombre": "Santa Cruz", "departamento": "Santa Cruz"},
    )
    assert response.status_code == 201
    return response.json()


def create_branch(client: TestClient, headers: dict[str, str], city_id: str) -> dict:
    response = client.post(
        "/api/v1/branches",
        headers=headers,
        json={
            "ciudad_id": city_id,
            "nombre": "Sucursal Centro",
            "direccion": "Av. Principal 100",
            "telefono": "33600000",
            "horario_informativo": "Lunes a sábado de 09:00 a 20:00",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_only_admin_can_manage_cities_and_branches(client: TestClient, db: Session) -> None:
    create_user(db, "cliente", "cliente@example.com")
    response = client.get(
        "/api/v1/cities",
        headers=headers_for(client, "cliente@example.com"),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_admin_can_create_search_update_and_deactivate_branch(client: TestClient, db: Session) -> None:
    create_user(db, "administrador", "admin@example.com")
    headers = headers_for(client, "admin@example.com")
    city = create_city(client, headers)
    branch = create_branch(client, headers, city["id"])

    city_list = client.get("/api/v1/cities?q=cruz", headers=headers)
    branch_list = client.get("/api/v1/branches?q=centro", headers=headers)
    update = client.patch(
        f"/api/v1/branches/{branch['id']}",
        headers=headers,
        json={"activa": False, "telefono": None},
    )

    assert city_list.status_code == 200 and city_list.json()["total"] == 1
    assert branch_list.status_code == 200 and branch_list.json()["total"] == 1
    assert branch_list.json()["items"][0]["ciudad"]["nombre"] == "Santa Cruz"
    assert update.status_code == 200
    assert update.json()["activa"] is False
    assert update.json()["telefono"] is None


def test_duplicates_and_deleting_city_with_branches_are_rejected(client: TestClient, db: Session) -> None:
    create_user(db, "administrador", "admin@example.com")
    headers = headers_for(client, "admin@example.com")
    city = create_city(client, headers)
    create_branch(client, headers, city["id"])

    duplicate_city = client.post(
        "/api/v1/cities",
        headers=headers,
        json={"nombre": "santa cruz"},
    )
    duplicate_branch = client.post(
        "/api/v1/branches",
        headers=headers,
        json={
            "ciudad_id": city["id"],
            "nombre": "sucursal centro",
            "direccion": "Otra dirección",
            "horario_informativo": "08:00 a 18:00",
        },
    )
    delete_city = client.delete(f"/api/v1/cities/{city['id']}", headers=headers)

    assert duplicate_city.status_code == 409
    assert duplicate_branch.status_code == 409
    assert delete_city.status_code == 409


def test_admin_can_assign_employee_only_to_an_active_existing_branch(
    client: TestClient, db: Session
) -> None:
    create_user(db, "administrador", "admin@example.com")
    headers = headers_for(client, "admin@example.com")
    city = create_city(client, headers)
    branch = create_branch(client, headers, city["id"])

    employee = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "cajero@example.com",
            "password": "ClaveCajero123",
            "nombres": "Carla",
            "apellidos": "Caja",
            "roles": ["cajero"],
            "sucursal_id": branch["id"],
        },
    )
    assert employee.status_code == 201
    assert employee.json()["sucursal_id"] == branch["id"]

    deactivate = client.patch(
        f"/api/v1/branches/{branch['id']}", headers=headers, json={"activa": False}
    )
    assert deactivate.status_code == 200

    another_employee = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "otro@example.com",
            "password": "ClaveCajero123",
            "nombres": "Otro",
            "apellidos": "Cajero",
            "roles": ["cajero"],
            "sucursal_id": branch["id"],
        },
    )
    assert another_employee.status_code == 409

    delete_assigned_branch = client.delete(f"/api/v1/branches/{branch['id']}", headers=headers)
    assert delete_assigned_branch.status_code == 409
