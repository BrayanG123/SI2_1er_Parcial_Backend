"""Persistencia y consultas de reservas."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.inventory.models import Inventario
from app.modules.reservations.models import DetalleReserva, EstadoReserva, Reserva


class ReservationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, reservation: Reserva) -> None:
        self.db.add(reservation)

    def get_by_id(self, reservation_id: UUID, *, for_update: bool = False) -> Reserva | None:
        statement = select(Reserva).where(Reserva.id == reservation_id)
        if for_update:
            statement = statement.with_for_update(of=Reserva)
        return self.db.scalar(statement.options(*self._options()))

    def list_for_customer(
        self, customer_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[Reserva], int]:
        filters = [Reserva.cliente_id == customer_id]
        return self._list(filters=filters, offset=offset, limit=limit)

    def list_for_branch(
        self,
        *,
        branch_id: UUID | None,
        state: EstadoReserva | None,
        visit_from: date | None,
        visit_to: date | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Reserva], int]:
        filters = []
        if branch_id is not None:
            filters.append(Reserva.sucursal_id == branch_id)
        if state is not None:
            filters.append(Reserva.estado == state.value)
        if visit_from is not None:
            filters.append(Reserva.fecha_visita >= visit_from)
        if visit_to is not None:
            filters.append(Reserva.fecha_visita <= visit_to)
        return self._list(filters=filters, offset=offset, limit=limit)

    def list_due(self, now: datetime, *, limit: int) -> list[Reserva]:
        statement = (
            select(Reserva)
            .where(
                Reserva.estado.in_(
                    (
                        EstadoReserva.PENDIENTE.value,
                        EstadoReserva.CONFIRMADA.value,
                        EstadoReserva.PREPARADA.value,
                    )
                ),
                Reserva.vence_en <= now,
            )
            .order_by(Reserva.vence_en, Reserva.id)
            .limit(limit)
            .with_for_update(of=Reserva, skip_locked=True)
            .options(*self._options())
        )
        return list(self.db.scalars(statement).unique())

    def _list(self, *, filters: list[object], offset: int, limit: int) -> tuple[list[Reserva], int]:
        statement = (
            select(Reserva)
            .where(*filters)
            .options(*self._options())
            .order_by(Reserva.creada_en.desc())
            .offset(offset)
            .limit(limit)
        )
        count_statement = select(func.count()).select_from(Reserva).where(*filters)
        return list(self.db.scalars(statement).unique()), self.db.scalar(count_statement) or 0

    @staticmethod
    def _options():
        return (
            joinedload(Reserva.cliente),
            joinedload(Reserva.sucursal),
            selectinload(Reserva.detalles)
            .joinedload(DetalleReserva.inventario)
            .joinedload(Inventario.variante),
        )
