"""Persistencia y consultas de devoluciones."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.catalog.models import VarianteProducto
from app.modules.orders.models import DetallePedido, Pedido
from app.modules.returns.models import DetalleDevolucion, Devolucion, EstadoDevolucion


class ReturnRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, return_request: Devolucion) -> None:
        self.db.add(return_request)

    def get_by_id(
        self, return_id: UUID, *, for_update: bool = False
    ) -> Devolucion | None:
        statement = select(Devolucion).where(Devolucion.id == return_id)
        if for_update:
            statement = statement.with_for_update(of=Devolucion)
        return self.db.scalar(
            statement.options(*self._options()).execution_options(populate_existing=True)
        )

    def list_for_customer(
        self, customer_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[Devolucion], int]:
        return self._list(
            filters=[Devolucion.cliente_id == customer_id], offset=offset, limit=limit
        )

    def list_manage(
        self,
        *,
        branch_id: UUID | None,
        state: EstadoDevolucion | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Devolucion], int]:
        filters = []
        if branch_id is not None:
            filters.append(Devolucion.pedido.has(Pedido.sucursal_id == branch_id))
        if state is not None:
            filters.append(Devolucion.estado == state.value)
        return self._list(filters=filters, offset=offset, limit=limit)

    def quantity_already_requested(self, order_detail_id: UUID) -> int:
        statement = (
            select(func.coalesce(func.sum(DetalleDevolucion.cantidad), 0))
            .join(DetalleDevolucion.devolucion)
            .where(
                DetalleDevolucion.detalle_pedido_id == order_detail_id,
                Devolucion.estado != EstadoDevolucion.CANCELADA.value,
            )
        )
        return int(self.db.scalar(statement) or 0)

    def _list(
        self, *, filters: list[object], offset: int, limit: int
    ) -> tuple[list[Devolucion], int]:
        statement = (
            select(Devolucion)
            .where(*filters)
            .options(*self._options())
            .order_by(Devolucion.creada_en.desc(), Devolucion.id.desc())
            .offset(offset)
            .limit(limit)
        )
        count = select(func.count()).select_from(Devolucion).where(*filters)
        return list(self.db.scalars(statement).unique()), self.db.scalar(count) or 0

    @staticmethod
    def _options():
        detail = selectinload(Devolucion.detalles).joinedload(
            DetalleDevolucion.detalle_pedido
        )
        return (
            joinedload(Devolucion.cliente),
            joinedload(Devolucion.pedido).joinedload(Pedido.sucursal),
            joinedload(Devolucion.reembolso),
            detail.joinedload(DetallePedido.variante).joinedload(
                VarianteProducto.producto
            ),
            detail.joinedload(DetallePedido.variante).joinedload(
                VarianteProducto.talla
            ),
            detail.joinedload(DetallePedido.variante).joinedload(
                VarianteProducto.color
            ),
        )
