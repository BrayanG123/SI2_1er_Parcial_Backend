"""Persistencia y consultas de pedidos."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.catalog.models import Producto, VarianteProducto
from app.modules.inventory.models import Inventario
from app.modules.orders.models import CanalPedido, DetallePedido, EstadoPedido, Pedido


class OrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, order: Pedido) -> None:
        self.db.add(order)

    def get_by_id(self, order_id: UUID, *, for_update: bool = False) -> Pedido | None:
        statement = select(Pedido).where(Pedido.id == order_id)
        if for_update:
            statement = statement.with_for_update(of=Pedido)
        return self.db.scalar(statement.options(*self._options()))

    def get_by_reservation(self, reservation_id: UUID) -> Pedido | None:
        return self.db.scalar(select(Pedido).where(Pedido.reserva_id == reservation_id))

    def list_for_customer(
        self, customer_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[Pedido], int]:
        return self._list(
            filters=[Pedido.cliente_id == customer_id], offset=offset, limit=limit
        )

    def list_manage(
        self,
        *,
        branch_id: UUID | None,
        channel: CanalPedido | None,
        state: EstadoPedido | None,
        date_from: date | None,
        date_to: date | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Pedido], int]:
        filters = []
        if branch_id is not None:
            filters.append(Pedido.sucursal_id == branch_id)
        if channel is not None:
            filters.append(Pedido.canal == channel.value)
        if state is not None:
            filters.append(Pedido.estado == state.value)
        if date_from is not None:
            filters.append(
                Pedido.creado_en >= datetime.combine(date_from, time.min, tzinfo=UTC)
            )
        if date_to is not None:
            filters.append(
                Pedido.creado_en
                < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC)
            )
        return self._list(filters=filters, offset=offset, limit=limit)

    def search_pos_inventory(
        self, *, branch_id: UUID, sku: str, limit: int = 20
    ) -> list[Inventario]:
        pattern = f"%{sku.strip()}%"
        statement = (
            select(Inventario)
            .join(Inventario.variante)
            .join(VarianteProducto.producto)
            .where(
                Inventario.sucursal_id == branch_id,
                VarianteProducto.sku.ilike(pattern),
                VarianteProducto.activa.is_(True),
                Producto.activo.is_(True),
                Producto.categoria.has(activa=True),
                Producto.proveedor.has(activo=True),
                Inventario.stock_fisico - Inventario.stock_reservado > 0,
            )
            .options(*self._inventory_options())
            .order_by(VarianteProducto.sku)
            .limit(limit)
        )
        return list(self.db.scalars(statement).unique())

    def _list(self, *, filters: list[object], offset: int, limit: int) -> tuple[list[Pedido], int]:
        statement = (
            select(Pedido)
            .where(*filters)
            .options(*self._options())
            .order_by(Pedido.creado_en.desc(), Pedido.id.desc())
            .offset(offset)
            .limit(limit)
        )
        count_statement = select(func.count()).select_from(Pedido).where(*filters)
        return list(self.db.scalars(statement).unique()), self.db.scalar(count_statement) or 0

    @staticmethod
    def _options():
        detail = selectinload(Pedido.detalles).joinedload(DetallePedido.variante)
        return (
            joinedload(Pedido.cliente),
            joinedload(Pedido.sucursal),
            detail.joinedload(VarianteProducto.producto),
            detail.joinedload(VarianteProducto.talla),
            detail.joinedload(VarianteProducto.color),
        )

    @staticmethod
    def _inventory_options():
        variant = joinedload(Inventario.variante)
        return (
            joinedload(Inventario.sucursal),
            variant.joinedload(VarianteProducto.producto),
            variant.joinedload(VarianteProducto.talla),
            variant.joinedload(VarianteProducto.color),
        )
