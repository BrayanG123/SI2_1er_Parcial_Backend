"""Consultas agregadas y controladas para reportes."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.branches.models import Sucursal
from app.modules.catalog.models import Producto, VarianteProducto
from app.modules.inventory.models import Inventario
from app.modules.orders.models import DetallePedido, EstadoPedido, Pedido
from app.modules.payments.models import Pago, Reembolso
from app.modules.reservations.models import DetalleReserva, Reserva
from app.modules.returns.models import DetalleDevolucion, Devolucion


SALE_STATES = (
    EstadoPedido.PAGADO.value,
    EstadoPedido.COMPLETADO.value,
    EstadoPedido.REEMBOLSADO.value,
)


def _period_filters(
    column, date_from: date | None, date_to: date | None  # type: ignore[no-untyped-def]
) -> list[object]:
    filters: list[object] = []
    if date_from is not None:
        filters.append(column >= datetime.combine(date_from, time.min, tzinfo=UTC))
    if date_to is not None:
        exclusive_end = datetime.combine(date_to, time.min, tzinfo=UTC) + timedelta(days=1)
        filters.append(column < exclusive_end)
    return filters


class ReportRepository:
    """Centraliza SQL estático; ningún texto del usuario se convierte en SQL."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _sales_filters(
        *, branch_id: UUID | None, date_from: date | None, date_to: date | None
    ) -> list[object]:
        filters: list[object] = [Pedido.estado.in_(SALE_STATES)]
        if branch_id is not None:
            filters.append(Pedido.sucursal_id == branch_id)
        filters.extend(_period_filters(Pedido.creado_en, date_from, date_to))
        return filters

    def sales_rows(
        self, *, branch_id: UUID | None, date_from: date | None, date_to: date | None
    ) -> list[object]:
        statement = (
            select(Pedido.id, Pedido.canal, Pedido.total, Pedido.creado_en)
            .where(*self._sales_filters(branch_id=branch_id, date_from=date_from, date_to=date_to))
            .order_by(Pedido.creado_en)
        )
        return list(self.db.execute(statement).all())

    def sales_by_product(
        self, *, branch_id: UUID | None, date_from: date | None, date_to: date | None
    ) -> list[object]:
        units = func.sum(DetallePedido.cantidad).label("unidades")
        amount = func.sum(DetallePedido.subtotal).label("monto")
        statement = (
            select(Producto.id, Producto.nombre, units, amount)
            .select_from(Pedido)
            .join(DetallePedido, DetallePedido.pedido_id == Pedido.id)
            .join(VarianteProducto, VarianteProducto.id == DetallePedido.variante_id)
            .join(Producto, Producto.id == VarianteProducto.producto_id)
            .where(*self._sales_filters(branch_id=branch_id, date_from=date_from, date_to=date_to))
            .group_by(Producto.id, Producto.nombre)
            .order_by(units.desc(), amount.desc(), Producto.nombre)
            .limit(10)
        )
        return list(self.db.execute(statement).all())

    def sales_units(
        self, *, branch_id: UUID | None, date_from: date | None, date_to: date | None
    ) -> int:
        statement = (
            select(func.coalesce(func.sum(DetallePedido.cantidad), 0))
            .select_from(DetallePedido)
            .join(Pedido, Pedido.id == DetallePedido.pedido_id)
            .where(
                *self._sales_filters(
                    branch_id=branch_id, date_from=date_from, date_to=date_to
                )
            )
        )
        return int(self.db.scalar(statement) or 0)

    def refunded_sales_total(
        self, *, branch_id: UUID | None, date_from: date | None, date_to: date | None
    ) -> Decimal:
        statement = (
            select(func.coalesce(func.sum(Reembolso.monto), 0))
            .select_from(Reembolso)
            .join(Pago, Pago.id == Reembolso.pago_id)
            .join(Pedido, Pedido.id == Pago.pedido_id)
            .where(*self._sales_filters(branch_id=branch_id, date_from=date_from, date_to=date_to))
        )
        return Decimal(self.db.scalar(statement) or 0)

    def inventory_rows(self, *, branch_id: UUID | None) -> list[object]:
        statement = (
            select(
                Inventario.id,
                Inventario.sucursal_id,
                Sucursal.nombre.label("sucursal_nombre"),
                Producto.id.label("producto_id"),
                Producto.nombre.label("producto_nombre"),
                VarianteProducto.id.label("variante_id"),
                VarianteProducto.sku,
                Inventario.stock_fisico,
                Inventario.stock_reservado,
                (Inventario.stock_fisico - Inventario.stock_reservado).label("stock_disponible"),
            )
            .select_from(Inventario)
            .join(Sucursal, Sucursal.id == Inventario.sucursal_id)
            .join(VarianteProducto, VarianteProducto.id == Inventario.variante_id)
            .join(Producto, Producto.id == VarianteProducto.producto_id)
        )
        if branch_id is not None:
            statement = statement.where(Inventario.sucursal_id == branch_id)
        statement = statement.order_by(
            (Inventario.stock_fisico - Inventario.stock_reservado),
            Producto.nombre,
            VarianteProducto.sku,
        )
        return list(self.db.execute(statement).all())

    def reservation_rows(
        self, *, branch_id: UUID | None, date_from: date | None, date_to: date | None
    ) -> list[object]:
        filters = self._reservation_filters(
            branch_id=branch_id, date_from=date_from, date_to=date_to
        )
        statement = select(Reserva.id, Reserva.estado, Reserva.creada_en).where(*filters)
        return list(self.db.execute(statement).all())

    def reservation_units(
        self, *, branch_id: UUID | None, date_from: date | None, date_to: date | None
    ) -> int:
        statement = (
            select(func.coalesce(func.sum(DetalleReserva.cantidad), 0))
            .select_from(DetalleReserva)
            .join(Reserva, Reserva.id == DetalleReserva.reserva_id)
            .where(
                *self._reservation_filters(
                    branch_id=branch_id, date_from=date_from, date_to=date_to
                )
            )
        )
        return int(self.db.scalar(statement) or 0)

    def converted_reservations(
        self, *, branch_id: UUID | None, date_from: date | None, date_to: date | None
    ) -> int:
        statement = (
            select(func.count(Pedido.id))
            .select_from(Reserva)
            .join(Pedido, Pedido.reserva_id == Reserva.id)
            .where(
                *self._reservation_filters(
                    branch_id=branch_id, date_from=date_from, date_to=date_to
                )
            )
        )
        return int(self.db.scalar(statement) or 0)

    @staticmethod
    def _reservation_filters(
        *, branch_id: UUID | None, date_from: date | None, date_to: date | None
    ) -> list[object]:
        filters: list[object] = []
        if branch_id is not None:
            filters.append(Reserva.sucursal_id == branch_id)
        filters.extend(_period_filters(Reserva.creada_en, date_from, date_to))
        return filters

    def return_rows(
        self, *, branch_id: UUID | None, date_from: date | None, date_to: date | None
    ) -> list[object]:
        statement = (
            select(Devolucion.id, Devolucion.estado, Devolucion.creada_en)
            .select_from(Devolucion)
            .join(Pedido, Pedido.id == Devolucion.pedido_id)
            .where(*self._return_filters(branch_id=branch_id, date_from=date_from, date_to=date_to))
        )
        return list(self.db.execute(statement).all())

    def return_units_and_amount(
        self, *, branch_id: UUID | None, date_from: date | None, date_to: date | None
    ) -> tuple[int, Decimal]:
        statement = (
            select(
                func.coalesce(func.sum(DetalleDevolucion.cantidad), 0),
                func.coalesce(
                    func.sum(DetalleDevolucion.cantidad * DetallePedido.precio_unitario), 0
                ),
            )
            .select_from(DetalleDevolucion)
            .join(Devolucion, Devolucion.id == DetalleDevolucion.devolucion_id)
            .join(Pedido, Pedido.id == Devolucion.pedido_id)
            .join(DetallePedido, DetallePedido.id == DetalleDevolucion.detalle_pedido_id)
            .where(*self._return_filters(branch_id=branch_id, date_from=date_from, date_to=date_to))
        )
        row = self.db.execute(statement).one()
        return int(row[0] or 0), Decimal(row[1] or 0)

    def return_refunded_total(
        self, *, branch_id: UUID | None, date_from: date | None, date_to: date | None
    ) -> Decimal:
        statement = (
            select(func.coalesce(func.sum(Reembolso.monto), 0))
            .select_from(Reembolso)
            .join(Devolucion, Devolucion.id == Reembolso.devolucion_id)
            .join(Pedido, Pedido.id == Devolucion.pedido_id)
            .where(*self._return_filters(branch_id=branch_id, date_from=date_from, date_to=date_to))
        )
        return Decimal(self.db.scalar(statement) or 0)

    @staticmethod
    def _return_filters(
        *, branch_id: UUID | None, date_from: date | None, date_to: date | None
    ) -> list[object]:
        filters: list[object] = []
        if branch_id is not None:
            filters.append(Pedido.sucursal_id == branch_id)
        filters.extend(_period_filters(Devolucion.creada_en, date_from, date_to))
        return filters
