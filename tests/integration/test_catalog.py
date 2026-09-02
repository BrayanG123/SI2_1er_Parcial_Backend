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
    email = f"catalog-{role_name}@example.com"
    db.add(
        Usuario(
            email=email,
            password_hash=hash_password("ClaveSegura123"),
            nombres="Usuario",
            apellidos="Catálogo",
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


def create_master_data(client: TestClient, headers: dict[str, str]) -> dict[str, dict]:
    calls = {
        "category": ("/api/v1/categories", {"nombre": "Vestidos"}),
        "supplier": ("/api/v1/suppliers", {"nombre": "Textiles Andinos"}),
        "size": ("/api/v1/admin/catalog/sizes", {"nombre": "M", "orden": 2}),
        "color": ("/api/v1/admin/catalog/colors", {"nombre": "Rojo", "codigo_hex": "#AA0000"}),
        "season": (
            "/api/v1/admin/catalog/seasons",
            {"nombre": "Primavera 2026", "fecha_inicio": "2026-09-01", "fecha_fin": "2026-11-30"},
        ),
    }
    result = {}
    for key, (url, payload) in calls.items():
        response = client.post(url, headers=headers, json=payload)
        assert response.status_code == 201, response.text
        result[key] = response.json()
    collection = client.post(
        "/api/v1/admin/catalog/collections",
        headers=headers,
        json={"temporada_id": result["season"]["id"], "nombre": "Noche"},
    )
    assert collection.status_code == 201, collection.text
    result["collection"] = collection.json()
    return result


def product_payload(master: dict[str, dict]) -> dict:
    return {
        "categoria_id": master["category"]["id"],
        "proveedor_id": master["supplier"]["id"],
        "temporada_id": master["season"]["id"],
        "coleccion_id": master["collection"]["id"],
        "nombre": "Vestido Aurora",
        "descripcion": "Vestido elegante para eventos",
        "marca": "Aurora",
        "precio_base": "250.00",
        "variantes": [
            {
                "talla_id": master["size"]["id"],
                "color_id": master["color"]["id"],
                "sku": "AUR-M-ROJO",
                "precio": "275.00",
            }
        ],
        "imagenes": [
            {"url": "https://images.example.com/aurora.jpg", "es_principal": True, "orden": 0}
        ],
    }


def test_catalog_administration_requires_admin_but_public_catalog_does_not(
    client: TestClient, db: Session
) -> None:
    headers = auth_headers(client, db, "cliente")
    assert client.get("/api/v1/admin/catalog/sizes", headers=headers).status_code == 403
    assert client.get("/api/v1/catalog/products").status_code == 200


def test_admin_manages_sizes_colors_seasons_and_collections(client: TestClient, db: Session) -> None:
    headers = auth_headers(client, db, "administrador")
    master = create_master_data(client, headers)

    invalid_dates = client.patch(
        f"/api/v1/admin/catalog/seasons/{master['season']['id']}",
        headers=headers,
        json={"fecha_inicio": "2026-12-20"},
    )
    collections = client.get(
        f"/api/v1/admin/catalog/collections?season_id={master['season']['id']}",
        headers=headers,
    )
    assert invalid_dates.status_code == 409
    assert collections.status_code == 200 and len(collections.json()) == 1


def test_admin_creates_product_and_public_can_search_and_filter_it(
    client: TestClient, db: Session
) -> None:
    headers = auth_headers(client, db, "administrador")
    master = create_master_data(client, headers)
    created = client.post(
        "/api/v1/admin/catalog/products", headers=headers, json=product_payload(master)
    )
    assert created.status_code == 201, created.text
    product = created.json()
    assert product["variantes"][0]["sku"] == "AUR-M-ROJO"
    assert product["imagenes"][0]["es_principal"] is True

    listing = client.get(
        "/api/v1/catalog/products",
        params={
            "q": "aurora",
            "category_id": master["category"]["id"],
            "season_id": master["season"]["id"],
            "size_id": master["size"]["id"],
            "color_id": master["color"]["id"],
        },
    )
    detail = client.get(f"/api/v1/catalog/products/{product['id']}")
    assert listing.status_code == 200 and listing.json()["total"] == 1
    assert detail.status_code == 200 and detail.json()["nombre"] == "Vestido Aurora"


def test_sku_and_size_color_combination_are_unique(client: TestClient, db: Session) -> None:
    headers = auth_headers(client, db, "administrador")
    master = create_master_data(client, headers)
    product = client.post(
        "/api/v1/admin/catalog/products", headers=headers, json=product_payload(master)
    ).json()

    duplicate = client.post(
        f"/api/v1/admin/catalog/products/{product['id']}/variants",
        headers=headers,
        json={
            "talla_id": master["size"]["id"],
            "color_id": master["color"]["id"],
            "sku": "OTRO-SKU",
        },
    )
    delete_last = client.delete(
        f"/api/v1/admin/catalog/variants/{product['variantes'][0]['id']}", headers=headers
    )
    assert duplicate.status_code == 409
    assert delete_last.status_code == 409


def test_inactive_products_and_variants_are_hidden_from_public_catalog(
    client: TestClient, db: Session
) -> None:
    headers = auth_headers(client, db, "administrador")
    master = create_master_data(client, headers)
    product = client.post(
        "/api/v1/admin/catalog/products", headers=headers, json=product_payload(master)
    ).json()
    response = client.patch(
        f"/api/v1/admin/catalog/products/{product['id']}",
        headers=headers,
        json={"activo": False},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/catalog/products").json()["total"] == 0
    assert client.get(f"/api/v1/catalog/products/{product['id']}").status_code == 404
