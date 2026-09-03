"""Casos de uso del carrito de compras."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.cart.models import Carrito, DetalleCarrito
from app.modules.cart.repository import CartRepository
from app.modules.cart.schemas import DetalleCarritoCreate, DetalleCarritoUpdate
from app.modules.catalog.repository import CatalogRepository
from app.modules.users.models import Usuario


class CartService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.carts = CartRepository(db)
        self.catalog = CatalogRepository(db)

    def get(self, *, customer: Usuario) -> Carrito:
        cart = self.carts.get_active(customer.id)
        if cart is None:
            cart = Carrito(cliente_id=customer.id, activo=True)
            self.carts.add(cart)
            self._commit("No se pudo crear el carrito.")
        return self.carts.get_active(customer.id)  # type: ignore[return-value]

    def add_item(self, data: DetalleCarritoCreate, *, customer: Usuario) -> Carrito:
        variant = self._active_variant(data.variante_id)
        cart = self.carts.get_active(customer.id, for_update=True)
        if cart is None:
            cart = Carrito(cliente_id=customer.id, activo=True)
            self.carts.add(cart)
            self.db.flush()
        item = self.carts.get_item_by_variant(cart.id, variant.id)
        if item is None:
            self.carts.add(
                DetalleCarrito(carrito_id=cart.id, variante_id=variant.id, cantidad=data.cantidad)
            )
        else:
            if item.cantidad + data.cantidad > 100:
                raise ConflictError("La cantidad máxima por variante es 100.")
            item.cantidad += data.cantidad
        self._commit("No se pudo agregar la prenda al carrito.")
        return self.carts.get_active(customer.id)  # type: ignore[return-value]

    def update_item(
        self, item_id: UUID, data: DetalleCarritoUpdate, *, customer: Usuario
    ) -> Carrito:
        cart = self._active_cart(customer.id, for_update=True)
        item = self.carts.get_item(cart.id, item_id)
        if item is None:
            raise NotFoundError("Prenda del carrito no encontrada.")
        item.cantidad = data.cantidad
        self._commit("No se pudo actualizar el carrito.")
        return self.carts.get_active(customer.id)  # type: ignore[return-value]

    def remove_item(self, item_id: UUID, *, customer: Usuario) -> Carrito:
        cart = self._active_cart(customer.id, for_update=True)
        item = self.carts.get_item(cart.id, item_id)
        if item is None:
            raise NotFoundError("Prenda del carrito no encontrada.")
        self.carts.delete_item(item)
        self._commit("No se pudo retirar la prenda del carrito.")
        return self.carts.get_active(customer.id)  # type: ignore[return-value]

    def clear(self, *, customer: Usuario) -> Carrito:
        cart = self._active_cart(customer.id, for_update=True)
        self.carts.clear(cart)
        self._commit("No se pudo vaciar el carrito.")
        return self.carts.get_active(customer.id)  # type: ignore[return-value]

    def _active_cart(self, customer_id: UUID, *, for_update: bool) -> Carrito:
        cart = self.carts.get_active(customer_id, for_update=for_update)
        if cart is None:
            raise NotFoundError("Carrito activo no encontrado.")
        return cart

    def _active_variant(self, variant_id: UUID):  # type: ignore[no-untyped-def]
        variant = self.catalog.get_variant(variant_id)
        if variant is None:
            raise NotFoundError("Variante de producto no encontrada.")
        product = variant.producto
        if (
            not variant.activa
            or not product.activo
            or not product.categoria.activa
            or not product.proveedor.activo
        ):
            raise ConflictError("La prenda ya no está disponible en el catálogo.")
        return variant

    def _commit(self, message: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(message) from exc
