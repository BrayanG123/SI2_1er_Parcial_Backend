"""Casos de uso de devolución, reintegro de stock y reembolso."""

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.modules.inventory.service import InventoryService
from app.modules.orders.models import EstadoPedido, Pedido
from app.modules.orders.repository import OrderRepository
from app.modules.payments.models import EstadoPago
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.service import PaymentService
from app.modules.returns.models import DetalleDevolucion, Devolucion, EstadoDevolucion
from app.modules.returns.repository import ReturnRepository
from app.modules.returns.schemas import DevolucionCreate, TransicionDevolucionRequest
from app.modules.users.models import Usuario


MONEY = Decimal("0.01")
ELIGIBLE_ORDER_STATES = {
    EstadoPedido.PAGADO,
    EstadoPedido.COMPLETADO,
    EstadoPedido.REEMBOLSADO,
}
STAFF_TRANSITIONS = {
    EstadoDevolucion.SOLICITADA: {
        EstadoDevolucion.APROBADA,
        EstadoDevolucion.CANCELADA,
    },
    EstadoDevolucion.APROBADA: {
        EstadoDevolucion.COMPLETADA,
        EstadoDevolucion.CANCELADA,
    },
}


class ReturnService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.returns = ReturnRepository(db)
        self.orders = OrderRepository(db)
        self.payments = PaymentRepository(db)
        self.payment_service = PaymentService(db)
        self.inventory = InventoryService(db)

    def create(self, data: DevolucionCreate, *, user: Usuario) -> Devolucion:
        order = self._get_order(data.pedido_id, for_update=True)
        self._authorize_creation(order, user)
        if EstadoPedido(order.estado) not in ELIGIBLE_ORDER_STATES:
            raise ConflictError("El pedido debe estar pagado o completado para devolver prendas.")

        sold = {detail.id: detail for detail in order.detalles}
        requested_ids = {detail.detalle_pedido_id for detail in data.detalles}
        if not requested_ids.issubset(sold):
            raise ConflictError("La devolución contiene prendas ajenas al pedido.")
        for requested in data.detalles:
            already_requested = self.returns.quantity_already_requested(
                requested.detalle_pedido_id
            )
            if already_requested + requested.cantidad > sold[requested.detalle_pedido_id].cantidad:
                raise ConflictError("No puedes devolver más unidades de las compradas.")

        return_request = Devolucion(
            pedido_id=order.id,
            cliente_id=order.cliente_id,
            estado=EstadoDevolucion.SOLICITADA.value,
            motivo_general=(data.motivo_general.strip() if data.motivo_general else None),
            detalles=[
                DetalleDevolucion(
                    detalle_pedido_id=item.detalle_pedido_id,
                    cantidad=item.cantidad,
                    motivo=item.motivo.strip() if item.motivo else None,
                )
                for item in data.detalles
            ],
        )
        self.returns.add(return_request)
        return self._commit_and_reload(return_request)

    def list_mine(
        self, *, customer: Usuario, page: int, page_size: int
    ) -> tuple[list[Devolucion], int]:
        return self.returns.list_for_customer(
            customer.id, offset=(page - 1) * page_size, limit=page_size
        )

    def get_mine(self, return_id: UUID, *, customer: Usuario) -> Devolucion:
        return_request = self._get(return_id)
        if return_request.cliente_id != customer.id:
            raise NotFoundError("Devolución no encontrada.")
        return return_request

    def cancel_by_customer(
        self, return_id: UUID, *, customer: Usuario
    ) -> Devolucion:
        return_request = self._get(return_id, for_update=True)
        if return_request.cliente_id != customer.id:
            raise NotFoundError("Devolución no encontrada.")
        if return_request.estado != EstadoDevolucion.SOLICITADA.value:
            raise ConflictError("Solo una devolución solicitada puede cancelarse.")
        return_request.estado = EstadoDevolucion.CANCELADA.value
        return self._commit_and_reload(return_request)

    def list_manage(
        self,
        *,
        user: Usuario,
        page: int,
        page_size: int,
        branch_id: UUID | None,
        state: EstadoDevolucion | None,
    ) -> tuple[list[Devolucion], int]:
        branch_id = self._scoped_branch(user, branch_id)
        return self.returns.list_manage(
            branch_id=branch_id,
            state=state,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    def get_manage(self, return_id: UUID, *, user: Usuario) -> Devolucion:
        return_request = self._get(return_id)
        self._scoped_branch(user, return_request.pedido.sucursal_id)
        return return_request

    def transition(
        self,
        return_id: UUID,
        data: TransicionDevolucionRequest,
        *,
        user: Usuario,
    ) -> Devolucion:
        return_request = self._get(return_id, for_update=True)
        self._scoped_branch(user, return_request.pedido.sucursal_id)
        current = EstadoDevolucion(return_request.estado)
        if data.estado not in STAFF_TRANSITIONS.get(current, set()):
            raise ConflictError(
                f"No se permite cambiar la devolución de {current.value} a {data.estado.value}."
            )
        if data.estado != EstadoDevolucion.COMPLETADA:
            return_request.estado = data.estado.value
            return self._commit_and_reload(return_request)

        try:
            if data.reingresar_stock:
                for detail in sorted(
                    return_request.detalles,
                    key=lambda item: str(item.detalle_pedido.variante_id),
                ):
                    self.inventory.return_stock(
                        return_request.pedido.sucursal_id,
                        detail.detalle_pedido.variante_id,
                        detail.cantidad,
                        reference_id=return_request.id,
                    )
            if data.generar_reembolso:
                payment = self.payments.get_by_order(
                    return_request.pedido_id, for_update=True
                )
                if payment is None or payment.estado not in {
                    EstadoPago.APROBADO.value,
                    EstadoPago.REEMBOLSADO.value,
                }:
                    raise ConflictError(
                        "El pedido no tiene un pago aprobado para reembolsar."
                    )
                self.payment_service.refund_for_return(
                    payment, return_request, self._refund_amount(return_request)
                )
            return_request.reingresa_stock = data.reingresar_stock
            return_request.genera_reembolso = data.generar_reembolso
            return_request.estado = EstadoDevolucion.COMPLETADA.value
            return_request.completada_en = datetime.now(UTC)
            return self._commit_and_reload(return_request)
        except Exception:
            self.db.rollback()
            raise

    def _refund_amount(self, return_request: Devolucion) -> Decimal:
        order = return_request.pedido
        gross = return_request.monto_estimado
        if order.subtotal == 0:
            return Decimal("0.00")
        amount = (gross * order.total / order.subtotal).quantize(
            MONEY, rounding=ROUND_HALF_UP
        )
        payment = self.payments.get_by_order(order.id)
        if payment is None:
            return amount
        remaining = payment.monto - self.payments.refunded_total(payment.id)
        return min(amount, remaining)

    def _authorize_creation(self, order: Pedido, user: Usuario) -> None:
        roles = {role.nombre for role in user.roles}
        if "cliente" in roles and order.cliente_id == user.id:
            return
        if "administrador" in roles:
            return
        if roles.intersection({"encargado", "cajero"}):
            if user.sucursal_id is None or user.sucursal_id != order.sucursal_id:
                raise ForbiddenError("Solo puedes registrar devoluciones de tu sucursal.")
            return
        raise NotFoundError("Pedido no encontrado.")

    def _scoped_branch(self, user: Usuario, requested: UUID | None) -> UUID | None:
        if any(role.nombre == "administrador" for role in user.roles):
            return requested
        if user.sucursal_id is None:
            raise ForbiddenError("Tu usuario no tiene una sucursal asignada.")
        if requested is not None and requested != user.sucursal_id:
            raise ForbiddenError("Solo puedes gestionar devoluciones de tu sucursal.")
        return user.sucursal_id

    def _get_order(self, order_id: UUID, *, for_update: bool = False) -> Pedido:
        order = self.orders.get_by_id(order_id, for_update=for_update)
        if order is None:
            raise NotFoundError("Pedido no encontrado.")
        return order

    def _get(self, return_id: UUID, *, for_update: bool = False) -> Devolucion:
        return_request = self.returns.get_by_id(return_id, for_update=for_update)
        if return_request is None:
            raise NotFoundError("Devolución no encontrada.")
        return return_request

    def _commit_and_reload(self, return_request: Devolucion) -> Devolucion:
        try:
            self.db.flush()
            return_id = return_request.id
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("No se pudo guardar la devolución.") from exc
        return self.returns.get_by_id(return_id)  # type: ignore[return-value]
