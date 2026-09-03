"""Reglas transaccionales de creación y atención de reservas."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.modules.branches.repository import BranchRepository
from app.modules.inventory.service import InventoryService
from app.modules.reservations.models import DetalleReserva, EstadoReserva, Reserva
from app.modules.reservations.repository import ReservationRepository
from app.modules.reservations.schemas import ReservaCreate
from app.modules.users.models import Usuario


BOLIVIA_TZ = ZoneInfo("America/La_Paz")
ACTIVE_STATES = {
    EstadoReserva.PENDIENTE,
    EstadoReserva.CONFIRMADA,
    EstadoReserva.PREPARADA,
}
STAFF_TRANSITIONS = {
    EstadoReserva.PENDIENTE: {EstadoReserva.CONFIRMADA, EstadoReserva.CANCELADA},
    EstadoReserva.CONFIRMADA: {EstadoReserva.PREPARADA, EstadoReserva.CANCELADA},
    EstadoReserva.PREPARADA: {EstadoReserva.COMPLETADA, EstadoReserva.CANCELADA},
}


class ReservationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.reservations = ReservationRepository(db)
        self.branches = BranchRepository(db)
        self.inventory = InventoryService(db)

    def create(self, data: ReservaCreate, *, customer: Usuario) -> Reserva:
        branch = self.branches.get_by_id(data.sucursal_id)
        if branch is None:
            raise NotFoundError("Sucursal no encontrada.")
        if not branch.activa:
            raise ConflictError("La sucursal debe estar activa para recibir reservas.")
        today = datetime.now(BOLIVIA_TZ).date()
        if data.fecha_visita < today:
            raise ConflictError("La fecha de visita no puede estar en el pasado.")

        expires_at = datetime.combine(
            data.fecha_visita + timedelta(days=1), time.min, tzinfo=BOLIVIA_TZ
        ).astimezone(UTC)
        reservation = Reserva(
            cliente_id=customer.id,
            sucursal_id=data.sucursal_id,
            estado=EstadoReserva.PENDIENTE.value,
            fecha_visita=data.fecha_visita,
            hora_aproximada=data.hora_aproximada,
            vence_en=expires_at,
        )
        self.reservations.add(reservation)
        try:
            self.db.flush()
            for requested in sorted(data.detalles, key=lambda item: str(item.variante_id)):
                stock = self.inventory.reserve(
                    data.sucursal_id,
                    requested.variante_id,
                    requested.cantidad,
                    reference_id=reservation.id,
                )
                reservation.detalles.append(
                    DetalleReserva(inventario_id=stock.id, cantidad=requested.cantidad)
                )
            return self._commit_and_reload(reservation)
        except Exception:
            self.db.rollback()
            raise

    def list_mine(
        self, *, customer: Usuario, page: int, page_size: int
    ) -> tuple[list[Reserva], int]:
        return self.reservations.list_for_customer(
            customer.id, offset=(page - 1) * page_size, limit=page_size
        )

    def get_mine(self, reservation_id: UUID, *, customer: Usuario) -> Reserva:
        reservation = self._get(reservation_id)
        if reservation.cliente_id != customer.id:
            raise NotFoundError("Reserva no encontrada.")
        return reservation

    def list_branch(
        self,
        *,
        user: Usuario,
        page: int,
        page_size: int,
        branch_id: UUID | None,
        state: EstadoReserva | None,
        visit_from: date | None,
        visit_to: date | None,
    ) -> tuple[list[Reserva], int]:
        if visit_from and visit_to and visit_from > visit_to:
            raise ConflictError("La fecha inicial no puede ser posterior a la fecha final.")
        branch_id = self._scoped_branch(user, branch_id)
        return self.reservations.list_for_branch(
            branch_id=branch_id,
            state=state,
            visit_from=visit_from,
            visit_to=visit_to,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

    def get_branch(self, reservation_id: UUID, *, user: Usuario) -> Reserva:
        reservation = self._get(reservation_id)
        self._scoped_branch(user, reservation.sucursal_id)
        return reservation

    def cancel_by_customer(self, reservation_id: UUID, *, customer: Usuario) -> Reserva:
        reservation = self._get_locked(reservation_id)
        if reservation.cliente_id != customer.id:
            raise NotFoundError("Reserva no encontrada.")
        if EstadoReserva(reservation.estado) not in ACTIVE_STATES:
            raise ConflictError("La reserva ya no puede cancelarse.")
        return self._close(reservation, EstadoReserva.CANCELADA, cancelled=True)

    def transition(
        self, reservation_id: UUID, target: EstadoReserva, *, user: Usuario
    ) -> Reserva:
        reservation = self._get_locked(reservation_id)
        self._scoped_branch(user, reservation.sucursal_id)
        current = EstadoReserva(reservation.estado)
        if target not in STAFF_TRANSITIONS.get(current, set()):
            raise ConflictError(f"No se permite cambiar la reserva de {current.value} a {target.value}.")
        if target in {EstadoReserva.CANCELADA, EstadoReserva.COMPLETADA}:
            return self._close(
                reservation,
                target,
                cancelled=target == EstadoReserva.CANCELADA,
            )
        reservation.estado = target.value
        return self._commit_and_reload(reservation)

    def expire_due(self, *, now: datetime | None = None, limit: int = 100) -> int:
        cutoff = self._as_utc(now or datetime.now(UTC))
        reservations = self.reservations.list_due(cutoff, limit=limit)
        if not reservations:
            return 0
        try:
            for reservation in reservations:
                self._release_details(reservation)
                reservation.estado = EstadoReserva.VENCIDA.value
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return len(reservations)

    def _close(
        self, reservation: Reserva, target: EstadoReserva, *, cancelled: bool
    ) -> Reserva:
        try:
            self._release_details(reservation)
            reservation.estado = target.value
            reservation.cancelada_en = datetime.now(UTC) if cancelled else None
            return self._commit_and_reload(reservation)
        except Exception:
            self.db.rollback()
            raise

    def _release_details(self, reservation: Reserva) -> None:
        for detail in sorted(reservation.detalles, key=lambda item: str(item.inventario.variante_id)):
            self.inventory.release_reservation(
                reservation.sucursal_id,
                detail.inventario.variante_id,
                detail.cantidad,
                reference_id=reservation.id,
            )

    def _get(self, reservation_id: UUID) -> Reserva:
        reservation = self.reservations.get_by_id(reservation_id)
        if reservation is None:
            raise NotFoundError("Reserva no encontrada.")
        return reservation

    def _get_locked(self, reservation_id: UUID) -> Reserva:
        reservation = self.reservations.get_by_id(reservation_id, for_update=True)
        if reservation is None:
            raise NotFoundError("Reserva no encontrada.")
        return reservation

    def _commit_and_reload(self, reservation: Reserva) -> Reserva:
        reservation_id = reservation.id
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("No se pudo guardar la reserva.") from exc
        return self.reservations.get_by_id(reservation_id)  # type: ignore[return-value]

    def _scoped_branch(self, user: Usuario, requested: UUID | None) -> UUID | None:
        if any(role.nombre == "administrador" for role in user.roles):
            return requested
        if user.sucursal_id is None:
            raise ForbiddenError("Tu usuario no tiene una sucursal asignada.")
        if requested is not None and requested != user.sucursal_id:
            raise ForbiddenError("Solo puedes gestionar reservas de tu sucursal.")
        return user.sucursal_id

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
