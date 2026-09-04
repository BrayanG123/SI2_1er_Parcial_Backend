"""Persistencia de pagos y reembolsos."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.payments.models import Pago, Reembolso


class PaymentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_payment(self, payment: Pago) -> None:
        self.db.add(payment)

    def add_refund(self, refund: Reembolso) -> None:
        self.db.add(refund)

    def get_by_id(self, payment_id: UUID, *, for_update: bool = False) -> Pago | None:
        statement = select(Pago).where(Pago.id == payment_id)
        if for_update:
            statement = statement.with_for_update(of=Pago)
        return self.db.scalar(
            statement.options(*self._options()).execution_options(populate_existing=True)
        )

    def get_by_order(self, order_id: UUID, *, for_update: bool = False) -> Pago | None:
        statement = select(Pago).where(Pago.pedido_id == order_id)
        if for_update:
            statement = statement.with_for_update(of=Pago)
        return self.db.scalar(
            statement.options(*self._options()).execution_options(populate_existing=True)
        )

    def get_by_reference(self, reference: str, *, for_update: bool = False) -> Pago | None:
        statement = select(Pago).where(Pago.referencia_externa == reference)
        if for_update:
            statement = statement.with_for_update(of=Pago)
        return self.db.scalar(
            statement.options(*self._options()).execution_options(populate_existing=True)
        )

    def refunded_total(self, payment_id: UUID) -> Decimal:
        statement = select(func.coalesce(func.sum(Reembolso.monto), 0)).where(
            Reembolso.pago_id == payment_id
        )
        return Decimal(self.db.scalar(statement) or 0)

    @staticmethod
    def _options():
        return (
            joinedload(Pago.pedido),
            selectinload(Pago.reembolsos),
        )
