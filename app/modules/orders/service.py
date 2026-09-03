"""Compras web, móviles y POS con inventario transaccional."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.modules.branches.models import Sucursal
from app.modules.branches.repository import BranchRepository
from app.modules.cart.models import Carrito
from app.modules.cart.repository import CartRepository
from app.modules.catalog.models import VarianteProducto
from app.modules.catalog.repository import CatalogRepository
from app.modules.inventory.models import Inventario
from app.modules.inventory.service import InventoryService
from app.modules.orders.models import CanalPedido, DetallePedido, EstadoPedido, Pedido
from app.modules.orders.repository import OrderRepository
from app.modules.orders.schemas import (
    CheckoutCarritoRequest,
    CheckoutReservaRequest,
    VentaPosRequest,
)
from app.modules.payments.service import PaymentService
from app.modules.reservations.models import EstadoReserva, Reserva
from app.modules.reservations.repository import ReservationRepository
from app.modules.users.models import Usuario
from app.modules.users.repository import UserRepository


MONEY = Decimal("0.01")
ACTIVE_RESERVATIONS = {
    EstadoReserva.PENDIENTE,
    EstadoReserva.CONFIRMADA,
    EstadoReserva.PREPARADA,
}


class OrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.orders = OrderRepository(db)
        self.carts = CartRepository(db)
        self.catalog = CatalogRepository(db)
        self.branches = BranchRepository(db)
        self.users = UserRepository(db)
        self.reservations = ReservationRepository(db)
        self.inventory = InventoryService(db)

    def options(self, *, user: Usuario) -> list[Sucursal]:
        branch_id = self._scoped_branch(user, None) if self._is_branch_employee(user) else None
        if branch_id is not None:
            branch = self.branches.get_by_id(branch_id)
            return [branch] if branch and branch.activa else []
        branches, _ = self.branches.list(
            offset=0, limit=200, query=None, city_id=None, active=True
        )
        return branches

    def checkout_cart(self, data: CheckoutCarritoRequest, *, customer: Usuario) -> Pedido:
        cart = self.carts.get_active(customer.id, for_update=True)
        if cart is None or not cart.detalles:
            raise ConflictError("El carrito está vacío.")
        try:
            order = self._create_direct_order(
                branch_id=data.sucursal_id,
                customer=customer,
                channel=CanalPedido(data.canal),
                lines=[(item.variante_id, item.cantidad) for item in cart.detalles],
            )
            cart.activo = False
            return self._commit_and_reload(order)
        except Exception:
            self.db.rollback()
            raise

    def checkout_reservation(
        self,
        reservation_id: UUID,
        data: CheckoutReservaRequest,
        *,
        customer: Usuario,
    ) -> Pedido:
        reservation = self.reservations.get_by_id(reservation_id, for_update=True)
        if reservation is None or reservation.cliente_id != customer.id:
            raise NotFoundError("Reserva no encontrada.")
        if EstadoReserva(reservation.estado) not in ACTIVE_RESERVATIONS:
            raise ConflictError("La reserva ya no puede convertirse en pedido.")
        if self.orders.get_by_reservation(reservation.id) is not None:
            raise ConflictError("La reserva ya fue convertida en pedido.")

        requested = {item.variante_id: item.cantidad for item in data.detalles}
        reserved = {item.variante_id: item for item in reservation.detalles}
        if not set(requested).issubset(reserved):
            raise ConflictError("La selección contiene prendas ajenas a la reserva.")
        for variant_id, quantity in requested.items():
            if quantity > reserved[variant_id].cantidad:
                raise ConflictError("No puedes comprar más unidades que las reservadas.")

        try:
            self._active_branch(reservation.sucursal_id)
            prepared = [
                (self._active_variant(variant_id), quantity)
                for variant_id, quantity in requested.items()
            ]
            order = self._new_order(
                branch_id=reservation.sucursal_id,
                customer=customer,
                channel=CanalPedido(data.canal),
                state=EstadoPedido.CREADO,
                variants=prepared,
                reservation=reservation,
            )
            self.db.flush()
            for detail in sorted(
                reservation.detalles, key=lambda item: str(item.variante_id)
            ):
                sold = requested.get(detail.variante_id, 0)
                if sold:
                    self.inventory.sell(
                        reservation.sucursal_id,
                        detail.variante_id,
                        sold,
                        from_reservation=True,
                        reference_id=order.id,
                    )
                remaining = detail.cantidad - sold
                if remaining:
                    self.inventory.release_reservation(
                        reservation.sucursal_id,
                        detail.variante_id,
                        remaining,
                        reference_id=reservation.id,
                    )
            reservation.estado = EstadoReserva.COMPLETADA.value
            return self._commit_and_reload(order)
        except Exception:
            self.db.rollback()
            raise

    def create_pos(self, data: VentaPosRequest, *, user: Usuario) -> Pedido:
        branch_id = self._scoped_branch(user, data.sucursal_id)
        assert branch_id is not None
        customer = self._optional_customer(data.cliente_id)
        try:
            order = self._create_direct_order(
                branch_id=branch_id,
                customer=customer,
                channel=CanalPedido.POS,
                lines=[(item.variante_id, item.cantidad) for item in data.detalles],
            )
            order.estado = EstadoPedido.COMPLETADO.value
            PaymentService(self.db).record_pos_payment(order)
            return self._commit_and_reload(order)
        except Exception:
            self.db.rollback()
            raise

    def search_pos(
        self, *, user: Usuario, sku: str, branch_id: UUID | None
    ) -> list[Inventario]:
        if not sku.strip():
            raise ConflictError("Ingresa un SKU para buscar existencias.")
        scoped = self._scoped_branch(user, branch_id)
        if scoped is None:
            raise ConflictError("Selecciona una sucursal para buscar existencias.")
        return self.orders.search_pos_inventory(branch_id=scoped, sku=sku)

    def list_mine(
        self, *, customer: Usuario, page: int, page_size: int
    ) -> tuple[list[Pedido], int]:
        return self.orders.list_for_customer(
            customer.id, offset=(page - 1) * page_size, limit=page_size
        )

    def get_mine(self, order_id: UUID, *, customer: Usuario) -> Pedido:
        order = self._get(order_id)
        if order.cliente_id != customer.id:
            raise NotFoundError("Pedido no encontrado.")
        return order

    def list_manage(
        self,
        *,
        user: Usuario,
        page: int,
        page_size: int,
        branch_id: UUID | None,
        channel: CanalPedido | None,
        state: EstadoPedido | None,
        date_from: date | None,
        date_to: date | None,
    ) -> tuple[list[Pedido], int]:
        if date_from and date_to and date_from > date_to:
            raise ConflictError("La fecha inicial no puede ser posterior a la fecha final.")
        branch_id = self._scoped_branch(user, branch_id)
        return self.orders.list_manage(
            branch_id=branch_id,
            channel=channel,
            state=state,
            date_from=date_from,
            date_to=date_to,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    def get_manage(self, order_id: UUID, *, user: Usuario) -> Pedido:
        order = self._get(order_id)
        self._scoped_branch(user, order.sucursal_id)
        return order

    def _create_direct_order(
        self,
        *,
        branch_id: UUID,
        customer: Usuario | None,
        channel: CanalPedido,
        lines: list[tuple[UUID, int]],
    ) -> Pedido:
        self._active_branch(branch_id)
        prepared = [(self._active_variant(variant_id), quantity) for variant_id, quantity in lines]
        order = self._new_order(
            branch_id=branch_id,
            customer=customer,
            channel=channel,
            state=EstadoPedido.CREADO,
            variants=prepared,
        )
        self.db.flush()
        for variant, quantity in sorted(prepared, key=lambda item: str(item[0].id)):
            self.inventory.sell(
                branch_id, variant.id, quantity, reference_id=order.id
            )
        return order

    def _new_order(
        self,
        *,
        branch_id: UUID,
        customer: Usuario | None,
        channel: CanalPedido,
        state: EstadoPedido,
        variants: list[tuple[VarianteProducto, int]],
        reservation: Reserva | None = None,
    ) -> Pedido:
        details = []
        subtotal = Decimal("0.00")
        for variant, quantity in variants:
            unit_price = (variant.precio or variant.producto.precio_base).quantize(
                MONEY, rounding=ROUND_HALF_UP
            )
            line_subtotal = (unit_price * quantity).quantize(MONEY, rounding=ROUND_HALF_UP)
            subtotal += line_subtotal
            details.append(
                DetallePedido(
                    variante_id=variant.id,
                    cantidad=quantity,
                    precio_unitario=unit_price,
                    subtotal=line_subtotal,
                )
            )
        subtotal = subtotal.quantize(MONEY, rounding=ROUND_HALF_UP)
        order = Pedido(
            cliente_id=customer.id if customer else None,
            sucursal_id=branch_id,
            reserva_id=reservation.id if reservation else None,
            canal=channel.value,
            estado=state.value,
            subtotal=subtotal,
            descuento=Decimal("0.00"),
            total=subtotal,
            detalles=details,
        )
        self.orders.add(order)
        return order

    def _active_variant(self, variant_id: UUID) -> VarianteProducto:
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
            raise ConflictError("La prenda ya no está disponible para venderse.")
        return variant

    def _active_branch(self, branch_id: UUID) -> Sucursal:
        branch = self.branches.get_by_id(branch_id)
        if branch is None:
            raise NotFoundError("Sucursal no encontrada.")
        if not branch.activa:
            raise ConflictError("La sucursal no está activa.")
        return branch

    def _optional_customer(self, customer_id: UUID | None) -> Usuario | None:
        if customer_id is None:
            return None
        customer = self.users.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError("Cliente no encontrado.")
        if not customer.activo or not any(role.nombre == "cliente" for role in customer.roles):
            raise ConflictError("La cuenta seleccionada no es un cliente activo.")
        return customer

    def _get(self, order_id: UUID) -> Pedido:
        order = self.orders.get_by_id(order_id)
        if order is None:
            raise NotFoundError("Pedido no encontrado.")
        return order

    def _commit_and_reload(self, order: Pedido) -> Pedido:
        order_id = order.id
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("No se pudo registrar el pedido.") from exc
        return self.orders.get_by_id(order_id)  # type: ignore[return-value]

    def _scoped_branch(self, user: Usuario, requested: UUID | None) -> UUID | None:
        if self._is_admin(user) or not self._is_branch_employee(user):
            return requested
        if user.sucursal_id is None:
            raise ForbiddenError("Tu usuario no tiene una sucursal asignada.")
        if requested is not None and requested != user.sucursal_id:
            raise ForbiddenError("Solo puedes operar pedidos de tu sucursal.")
        return user.sucursal_id

    @staticmethod
    def _is_admin(user: Usuario) -> bool:
        return any(role.nombre == "administrador" for role in user.roles)

    @staticmethod
    def _is_branch_employee(user: Usuario) -> bool:
        return any(role.nombre in {"encargado", "cajero"} for role in user.roles)
