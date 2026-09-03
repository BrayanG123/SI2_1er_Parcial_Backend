"""Casos de uso transaccionales de pagos y reembolsos."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.integrations.payment_gateway.client import (
    GatewayPaymentStatus,
    PaymentGateway,
    TestPaymentGateway,
)
from app.modules.inventory.service import InventoryService
from app.modules.orders.models import CanalPedido, EstadoPedido, Pedido
from app.modules.orders.repository import OrderRepository
from app.modules.payments.models import EstadoPago, MetodoPago, Pago, Reembolso
from app.modules.payments.repository import PaymentRepository
from app.modules.returns.models import Devolucion
from app.modules.users.models import Usuario


class PaymentService:
    def __init__(
        self, db: Session, *, gateway: PaymentGateway | None = None
    ) -> None:
        self.db = db
        self.payments = PaymentRepository(db)
        self.orders = OrderRepository(db)
        self.inventory = InventoryService(db)
        self.gateway = gateway or TestPaymentGateway()

    def get_for_order(self, order_id: UUID, *, user: Usuario) -> Pago | None:
        order = self._get_order(order_id)
        self._authorize_order(order, user)
        return self.payments.get_by_order(order_id)

    def initiate(self, order_id: UUID, *, customer: Usuario) -> Pago:
        order = self._get_order(order_id, for_update=True)
        self._authorize_customer_order(order, customer)
        if order.canal not in {CanalPedido.WEB.value, CanalPedido.MOBILE.value}:
            raise ConflictError("Solo los pedidos digitales usan la pasarela de prueba.")
        if order.estado != EstadoPedido.CREADO.value:
            raise ConflictError("El pedido ya no admite iniciar un pago.")
        if self.payments.get_by_order(order.id) is not None:
            raise ConflictError("El pedido ya tiene un intento de pago registrado.")

        payment = Pago(
            pedido_id=order.id,
            metodo=MetodoPago.PASARELA_PRUEBA.value,
            estado=EstadoPago.PENDIENTE.value,
            monto=order.total,
            referencia_externa=self.gateway.initiate(
                order_id=order.id, amount=order.total
            ),
        )
        self.payments.add_payment(payment)
        return self._commit_and_reload(payment)

    def confirm(
        self, payment_id: UUID, *, approve: bool, customer: Usuario
    ) -> Pago:
        payment = self._get_payment(payment_id, for_update=True)
        self._authorize_customer_order(payment.pedido, customer)
        if payment.metodo != MetodoPago.PASARELA_PRUEBA.value:
            raise ConflictError("Este pago no pertenece a la pasarela de prueba.")
        if payment.estado != EstadoPago.PENDIENTE.value:
            raise ConflictError("El pago ya fue confirmado.")
        assert payment.referencia_externa is not None

        result = self.gateway.confirm(
            reference=payment.referencia_externa, approve=approve
        )
        try:
            if result.status == GatewayPaymentStatus.APPROVED:
                payment.estado = EstadoPago.APROBADO.value
                payment.pagado_en = datetime.now(UTC)
                payment.pedido.estado = EstadoPedido.PAGADO.value
            else:
                self._restore_rejected_order(payment.pedido, payment.id)
                payment.estado = EstadoPago.RECHAZADO.value
                payment.pedido.estado = EstadoPedido.CANCELADO.value
            return self._commit_and_reload(payment)
        except Exception:
            self.db.rollback()
            raise

    def record_pos_payment(self, order: Pedido) -> Pago:
        payment = Pago(
            pedido_id=order.id,
            metodo=MetodoPago.CAJA.value,
            estado=EstadoPago.APROBADO.value,
            monto=order.total,
            referencia_externa=f"POS-{order.id}",
            pagado_en=datetime.now(UTC),
        )
        self.payments.add_payment(payment)
        return payment

    def refund_for_return(
        self, payment: Pago, return_request: Devolucion, amount: Decimal
    ) -> Reembolso:
        if payment.estado not in {
            EstadoPago.APROBADO.value,
            EstadoPago.REEMBOLSADO.value,
        }:
            raise ConflictError("El pedido no tiene un pago aprobado para reembolsar.")
        refunded = self.payments.refunded_total(payment.id)
        if refunded + amount > payment.monto:
            raise ConflictError("El reembolso excedería el monto pagado.")
        if payment.metodo == MetodoPago.PASARELA_PRUEBA.value:
            assert payment.referencia_externa is not None
            reference = self.gateway.refund(
                reference=payment.referencia_externa, amount=amount
            )
        else:
            reference = f"POS-REF-{return_request.id}"
        refund = Reembolso(
            pago_id=payment.id,
            devolucion_id=return_request.id,
            monto=amount,
            motivo=return_request.motivo_general or "Devolución de prendas",
            referencia_externa=reference,
        )
        self.payments.add_refund(refund)
        if refunded + amount == payment.monto:
            payment.estado = EstadoPago.REEMBOLSADO.value
            payment.pedido.estado = EstadoPedido.REEMBOLSADO.value
        return refund

    def _restore_rejected_order(self, order: Pedido, payment_id: UUID) -> None:
        for detail in sorted(order.detalles, key=lambda item: str(item.variante_id)):
            self.inventory.return_stock(
                order.sucursal_id,
                detail.variante_id,
                detail.cantidad,
                reference_id=payment_id,
                reference_type="PAGO",
                observation="Reposición automática por pago rechazado",
            )

    def _get_payment(self, payment_id: UUID, *, for_update: bool = False) -> Pago:
        payment = self.payments.get_by_id(payment_id, for_update=for_update)
        if payment is None:
            raise NotFoundError("Pago no encontrado.")
        return payment

    def _get_order(self, order_id: UUID, *, for_update: bool = False) -> Pedido:
        order = self.orders.get_by_id(order_id, for_update=for_update)
        if order is None:
            raise NotFoundError("Pedido no encontrado.")
        return order

    def _authorize_customer_order(self, order: Pedido, customer: Usuario) -> None:
        if order.cliente_id != customer.id:
            raise NotFoundError("Pedido no encontrado.")

    def _authorize_order(self, order: Pedido, user: Usuario) -> None:
        roles = {role.nombre for role in user.roles}
        if "cliente" in roles and order.cliente_id == user.id:
            return
        if "administrador" in roles:
            return
        if roles.intersection({"encargado", "cajero"}):
            if user.sucursal_id is None or user.sucursal_id != order.sucursal_id:
                raise ForbiddenError("Solo puedes consultar pagos de tu sucursal.")
            return
        raise NotFoundError("Pedido no encontrado.")

    def _commit_and_reload(self, payment: Pago) -> Pago:
        try:
            self.db.flush()
            payment_id = payment.id
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("No se pudo registrar el pago.") from exc
        return self.payments.get_by_id(payment_id)  # type: ignore[return-value]
