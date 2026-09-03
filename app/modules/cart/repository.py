"""Persistencia de carritos."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.cart.models import Carrito, DetalleCarrito
from app.modules.catalog.models import VarianteProducto


class CartRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active(self, customer_id: UUID, *, for_update: bool = False) -> Carrito | None:
        statement = select(Carrito).where(
            Carrito.cliente_id == customer_id, Carrito.activo.is_(True)
        )
        if for_update:
            statement = statement.with_for_update(of=Carrito)
        return self.db.scalar(
            statement.options(*self._options()).execution_options(populate_existing=True)
        )

    def get_item(self, cart_id: UUID, item_id: UUID) -> DetalleCarrito | None:
        return self.db.scalar(
            select(DetalleCarrito).where(
                DetalleCarrito.id == item_id, DetalleCarrito.carrito_id == cart_id
            )
        )

    def get_item_by_variant(self, cart_id: UUID, variant_id: UUID) -> DetalleCarrito | None:
        return self.db.scalar(
            select(DetalleCarrito).where(
                DetalleCarrito.carrito_id == cart_id,
                DetalleCarrito.variante_id == variant_id,
            )
        )

    def add(self, entity: Carrito | DetalleCarrito) -> None:
        self.db.add(entity)

    def delete_item(self, item: DetalleCarrito) -> None:
        self.db.delete(item)

    def clear(self, cart: Carrito) -> None:
        for item in list(cart.detalles):
            self.db.delete(item)

    @staticmethod
    def _options():
        return (
            selectinload(Carrito.detalles)
            .joinedload(DetalleCarrito.variante)
            .joinedload(VarianteProducto.producto),
            selectinload(Carrito.detalles)
            .joinedload(DetalleCarrito.variante)
            .joinedload(VarianteProducto.talla),
            selectinload(Carrito.detalles)
            .joinedload(DetalleCarrito.variante)
            .joinedload(VarianteProducto.color),
        )
