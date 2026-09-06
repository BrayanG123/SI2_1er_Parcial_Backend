"""Prueba el seeder completo sobre una base efímera."""

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.branches.models import Ciudad, Sucursal
from app.modules.catalog.models import Producto, VarianteProducto
from app.modules.catalog.schemas import ProductoPage
from app.modules.inventory.models import Inventario
from app.modules.orders.models import DetallePedido, Pedido
from app.modules.payments.models import Pago, Reembolso
from app.modules.returns.models import Devolucion
from app.modules.suppliers.models import Proveedor
from app.modules.suppliers.schemas import ProveedorRead
from app.modules.users.models import Usuario
from app.modules.users.schemas import UsuarioRead
from app.scripts.seed_demo import (
    DEMO_EMAIL_SUFFIX,
    SeedConfig,
    SeedDataExistsError,
    repair_legacy_demo_emails,
    seed_database,
)
from tests.integration.test_auth_users import db


def test_seed_demo_populates_coherent_data_and_refuses_duplicates(db: Session) -> None:
    config = SeedConfig(
        seed=1234,
        anchor_date=date(2026, 9, 6),
        city_count=2,
        branch_count=2,
        client_count=6,
        product_count=8,
        order_count=10,
        reservation_count=3,
        return_count=4,
        cart_count=2,
    )

    result = seed_database(db, config, password="DemoSegura123")
    db.commit()

    assert result.inserted_rows > 200
    assert db.scalar(select(func.count()).select_from(Ciudad)) == 2
    assert db.scalar(select(func.count()).select_from(Sucursal)) == 2
    assert db.scalar(select(func.count()).select_from(Producto)) == 8
    assert db.scalar(select(func.count()).select_from(VarianteProducto)) == 24
    assert db.scalar(select(func.count()).select_from(Pedido)) == 10
    assert db.scalar(select(func.count()).select_from(Pago)) == 10
    assert db.scalar(select(func.count()).select_from(Devolucion)) == 4
    assert db.scalar(select(func.count()).select_from(Reembolso)) == 1
    assert db.scalar(
        select(func.count())
        .select_from(Usuario)
        .where(Usuario.email.endswith(DEMO_EMAIL_SUFFIX))
    ) == 11

    inventories = list(db.scalars(select(Inventario)))
    assert inventories
    assert all(
        0 <= item.stock_reservado <= item.stock_fisico for item in inventories
    )
    assert all(
        order.total == order.subtotal - order.descuento
        for order in db.scalars(select(Pedido))
    )
    assert all(
        detail.subtotal == detail.precio_unitario * detail.cantidad
        for detail in db.scalars(select(DetallePedido))
    )

    users = list(db.scalars(select(Usuario)))
    suppliers = list(db.scalars(select(Proveedor)))
    products = list(db.scalars(select(Producto)))
    assert all(UsuarioRead.model_validate(user) for user in users)
    assert all(ProveedorRead.model_validate(supplier) for supplier in suppliers)
    product_page = ProductoPage.model_validate(
        {
            "items": products,
            "page": 1,
            "page_size": len(products),
            "total": len(products),
        }
    )
    assert len(product_page.items) == 8

    with pytest.raises(SeedDataExistsError, match="tablas de negocio vacías"):
        seed_database(db, config, password="DemoSegura123")

    admin = db.scalar(
        select(Usuario).where(Usuario.email == "admin@demo.example.com")
    )
    first_supplier = db.scalar(
        select(Proveedor).where(
            Proveedor.email == "proveedor01@demo.example.com"
        )
    )
    assert admin is not None
    assert first_supplier is not None
    admin.email = "admin.demo@ropa.test"
    first_supplier.email = "proveedor01@ropa.test"
    db.commit()

    repaired = repair_legacy_demo_emails(db)
    db.commit()

    assert repaired.users == 1
    assert repaired.suppliers == 1
    assert admin.email == "admin@demo.example.com"
    assert first_supplier.email == "proveedor01@demo.example.com"
    assert repair_legacy_demo_emails(db).updated_rows == 0
