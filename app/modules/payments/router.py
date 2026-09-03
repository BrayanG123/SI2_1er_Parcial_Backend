"""Endpoints de pagos y reembolsos."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import CurrentUser, require_roles
from app.modules.payments.schemas import ConfirmacionPagoPruebaRequest, PagoRead
from app.modules.payments.service import PaymentService
from app.modules.users.models import Usuario


router = APIRouter(prefix="/payments", tags=["payments"])
Customer = Annotated[Usuario, Depends(require_roles("cliente"))]


@router.get("/orders/{order_id}", response_model=PagoRead | None)
def get_order_payment(
    order_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> PagoRead | None:
    payment = PaymentService(db).get_for_order(order_id, user=current_user)
    return PagoRead.model_validate(payment) if payment else None


@router.post(
    "/orders/{order_id}", response_model=PagoRead, status_code=status.HTTP_201_CREATED
)
def initiate_payment(
    order_id: UUID,
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
) -> PagoRead:
    return PagoRead.model_validate(
        PaymentService(db).initiate(order_id, customer=current_user)
    )


@router.post("/{payment_id}/confirm", response_model=PagoRead)
def confirm_payment(
    payment_id: UUID,
    data: ConfirmacionPagoPruebaRequest,
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
) -> PagoRead:
    return PagoRead.model_validate(
        PaymentService(db).confirm(
            payment_id,
            approve=data.resultado_prueba == "APROBAR",
            customer=current_user,
        )
    )
