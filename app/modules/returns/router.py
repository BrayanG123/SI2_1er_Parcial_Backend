"""Endpoints de devoluciones."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import CurrentUser, require_roles
from app.modules.returns.models import EstadoDevolucion
from app.modules.returns.schemas import (
    DevolucionCreate,
    DevolucionPage,
    DevolucionRead,
    TransicionDevolucionRequest,
)
from app.modules.returns.service import ReturnService
from app.modules.users.models import Usuario


router = APIRouter(prefix="/returns", tags=["returns"])
Customer = Annotated[Usuario, Depends(require_roles("cliente"))]
Creator = Annotated[
    Usuario,
    Depends(require_roles("cliente", "administrador", "encargado", "cajero")),
]
Manager = Annotated[
    Usuario, Depends(require_roles("administrador", "encargado"))
]


@router.post("", response_model=DevolucionRead, status_code=status.HTTP_201_CREATED)
def create_return(
    data: DevolucionCreate,
    current_user: Creator,
    db: Annotated[Session, Depends(get_db)],
) -> DevolucionRead:
    return DevolucionRead.model_validate(
        ReturnService(db).create(data, user=current_user)
    )


@router.get("/mine", response_model=DevolucionPage)
def list_my_returns(
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DevolucionPage:
    items, total = ReturnService(db).list_mine(
        customer=current_user, page=page, page_size=page_size
    )
    return DevolucionPage(
        items=items, page=page, page_size=page_size, total=total
    )


@router.get("/mine/{return_id}", response_model=DevolucionRead)
def get_my_return(
    return_id: UUID,
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
) -> DevolucionRead:
    return DevolucionRead.model_validate(
        ReturnService(db).get_mine(return_id, customer=current_user)
    )


@router.post("/{return_id}/cancel", response_model=DevolucionRead)
def cancel_my_return(
    return_id: UUID,
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
) -> DevolucionRead:
    return DevolucionRead.model_validate(
        ReturnService(db).cancel_by_customer(return_id, customer=current_user)
    )


@router.get("/manage", response_model=DevolucionPage)
def list_managed_returns(
    current_user: Manager,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    branch_id: UUID | None = None,
    state: EstadoDevolucion | None = None,
) -> DevolucionPage:
    items, total = ReturnService(db).list_manage(
        user=current_user,
        page=page,
        page_size=page_size,
        branch_id=branch_id,
        state=state,
    )
    return DevolucionPage(
        items=items, page=page, page_size=page_size, total=total
    )


@router.get("/manage/{return_id}", response_model=DevolucionRead)
def get_managed_return(
    return_id: UUID,
    current_user: Manager,
    db: Annotated[Session, Depends(get_db)],
) -> DevolucionRead:
    return DevolucionRead.model_validate(
        ReturnService(db).get_manage(return_id, user=current_user)
    )


@router.patch("/manage/{return_id}/status", response_model=DevolucionRead)
def transition_return(
    return_id: UUID,
    data: TransicionDevolucionRequest,
    current_user: Manager,
    db: Annotated[Session, Depends(get_db)],
) -> DevolucionRead:
    return DevolucionRead.model_validate(
        ReturnService(db).transition(return_id, data, user=current_user)
    )
