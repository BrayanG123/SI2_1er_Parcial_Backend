"""Persistencia y bloqueo transaccional de existencias."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.modules.branches.models import Sucursal
from app.modules.catalog.models import Producto, VarianteProducto
from app.modules.inventory.models import Inventario, MovimientoInventario
from app.modules.inventory.schemas import EstadoStock


class InventoryRepository:
    LOW_STOCK_LIMIT = 5

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, inventory_id: UUID) -> Inventario | None:
        statement = (
            select(Inventario)
            .where(Inventario.id == inventory_id)
            .options(*self._inventory_options())
        )
        return self.db.scalar(statement)

    def get_by_branch_variant(
        self, branch_id: UUID, variant_id: UUID, *, for_update: bool = False
    ) -> Inventario | None:
        statement = select(Inventario).where(
            Inventario.sucursal_id == branch_id,
            Inventario.variante_id == variant_id,
        )
        if for_update:
            statement = statement.with_for_update(of=Inventario)
        return self.db.scalar(statement.options(*self._inventory_options()))

    def list(
        self,
        *,
        offset: int,
        limit: int,
        branch_id: UUID | None,
        city_id: UUID | None,
        product_id: UUID | None,
        variant_id: UUID | None,
        state: EstadoStock | None,
    ) -> tuple[list[Inventario], int]:
        filters = []
        if branch_id:
            filters.append(Inventario.sucursal_id == branch_id)
        if city_id:
            filters.append(Inventario.sucursal.has(ciudad_id=city_id))
        if product_id:
            filters.append(Inventario.variante.has(producto_id=product_id))
        if variant_id:
            filters.append(Inventario.variante_id == variant_id)
        available = Inventario.stock_fisico - Inventario.stock_reservado
        if state == EstadoStock.DISPONIBLE:
            filters.append(available > self.LOW_STOCK_LIMIT)
        elif state == EstadoStock.BAJO:
            filters.extend((available > 0, available <= self.LOW_STOCK_LIMIT))
        elif state == EstadoStock.AGOTADO:
            filters.append(available == 0)
        statement = (
            select(Inventario)
            .where(*filters)
            .options(*self._inventory_options())
            .order_by(Inventario.actualizado_en.desc())
            .offset(offset)
            .limit(limit)
        )
        count_statement = select(func.count()).select_from(Inventario).where(*filters)
        return list(self.db.scalars(statement).unique()), self.db.scalar(count_statement) or 0

    def list_public_availability(self, product_id: UUID) -> list[Inventario]:
        statement = (
            select(Inventario)
            .join(Inventario.sucursal)
            .join(Inventario.variante)
            .join(VarianteProducto.producto)
            .where(
                Producto.id == product_id,
                Producto.activo.is_(True),
                Producto.categoria.has(activa=True),
                Producto.proveedor.has(activo=True),
                or_(Producto.temporada_id.is_(None), Producto.temporada.has(activa=True)),
                Sucursal.activa.is_(True),
                VarianteProducto.activa.is_(True),
            )
            .options(*self._inventory_options())
            .order_by(Sucursal.nombre, VarianteProducto.sku)
        )
        return list(self.db.scalars(statement).unique())

    def list_movements(
        self, inventory_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[MovimientoInventario], int]:
        statement = (
            select(MovimientoInventario)
            .where(MovimientoInventario.inventario_id == inventory_id)
            .order_by(MovimientoInventario.creado_en.desc())
            .offset(offset)
            .limit(limit)
        )
        count_statement = select(func.count()).select_from(MovimientoInventario).where(
            MovimientoInventario.inventario_id == inventory_id
        )
        return list(self.db.scalars(statement)), self.db.scalar(count_statement) or 0

    def add_inventory(self, inventory: Inventario) -> None:
        self.db.add(inventory)

    def add_movement(self, movement: MovimientoInventario) -> None:
        self.db.add(movement)

    @staticmethod
    def _inventory_options():
        return (
            joinedload(Inventario.sucursal).joinedload(Sucursal.ciudad),
            joinedload(Inventario.variante).joinedload(VarianteProducto.talla),
            joinedload(Inventario.variante).joinedload(VarianteProducto.color),
            joinedload(Inventario.variante).joinedload(VarianteProducto.producto),
        )
