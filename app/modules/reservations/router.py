"""Endpoints de clientes y sucursales para gestionar reservas."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError
from app.db.session import get_db
from app.modules.auth.dependencies import CurrentUser, require_roles
from app.modules.reservations.models import EstadoReserva
from app.modules.reservations.schemas import (
    ReservaCreate,
    ReservaPage,
    ReservaRead,
    TransicionReservaRequest,
)
from app.modules.reservations.service import ReservationService
from app.modules.users.models import Usuario


router = APIRouter(prefix="/reservations", tags=["reservations"])
Customer = Annotated[Usuario, Depends(require_roles("cliente"))]
Staff = Annotated[Usuario, Depends(require_roles("administrador", "encargado"))]


@router.post("", response_model=ReservaRead, status_code=status.HTTP_201_CREATED)
def create_reservation(
    data: ReservaCreate,
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
) -> ReservaRead:
    return ReservaRead.model_validate(ReservationService(db).create(data, customer=current_user))


@router.get("/mine", response_model=ReservaPage)
def list_my_reservations(
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReservaPage:
    items, total = ReservationService(db).list_mine(
        customer=current_user, page=page, page_size=page_size
    )
    return ReservaPage(items=items, page=page, page_size=page_size, total=total)


@router.get("/mine/{reservation_id}", response_model=ReservaRead)
def get_my_reservation(
    reservation_id: UUID,
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
) -> ReservaRead:
    return ReservaRead.model_validate(
        ReservationService(db).get_mine(reservation_id, customer=current_user)
    )


@router.post("/{reservation_id}/cancel", response_model=ReservaRead)
def cancel_reservation(
    reservation_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ReservaRead:
    service = ReservationService(db)
    roles = {role.nombre for role in current_user.roles}
    if roles.intersection({"administrador", "encargado"}):
        result = service.transition(
            reservation_id, EstadoReserva.CANCELADA, user=current_user
        )
    elif "cliente" in roles:
        result = service.cancel_by_customer(reservation_id, customer=current_user)
    else:
        raise ForbiddenError()
    return ReservaRead.model_validate(result)


@router.get("/branch", response_model=ReservaPage)
def list_branch_reservations(
    current_user: Staff,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    branch_id: UUID | None = None,
    state: EstadoReserva | None = None,
    visit_from: date | None = None,
    visit_to: date | None = None,
) -> ReservaPage:
    items, total = ReservationService(db).list_branch(
        user=current_user,
        page=page,
        page_size=page_size,
        branch_id=branch_id,
        state=state,
        visit_from=visit_from,
        visit_to=visit_to,
    )
    return ReservaPage(items=items, page=page, page_size=page_size, total=total)


@router.get("/branch/{reservation_id}", response_model=ReservaRead)
def get_branch_reservation(
    reservation_id: UUID,
    current_user: Staff,
    db: Annotated[Session, Depends(get_db)],
) -> ReservaRead:
    return ReservaRead.model_validate(
        ReservationService(db).get_branch(reservation_id, user=current_user)
    )


@router.patch("/branch/{reservation_id}/status", response_model=ReservaRead)
def transition_reservation(
    reservation_id: UUID,
    data: TransicionReservaRequest,
    current_user: Staff,
    db: Annotated[Session, Depends(get_db)],
) -> ReservaRead:
    return ReservaRead.model_validate(
        ReservationService(db).transition(reservation_id, data.estado, user=current_user)
    )
