"""Endpoints de pagos y reembolsos."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.integrations.payment_gateway.client import PaymentGateway
from app.integrations.payment_gateway.factory import get_payment_gateway
from app.modules.auth.dependencies import CurrentUser, require_roles
from app.modules.payments.schemas import (
    ConfirmacionPagoPruebaRequest,
    PagoRead,
    StripeWebhookRead,
)
from app.modules.payments.service import PaymentInitiation, PaymentService
from app.modules.users.models import Usuario


router = APIRouter(prefix="/payments", tags=["payments"])
Customer = Annotated[Usuario, Depends(require_roles("cliente"))]
GatewayDependency = Annotated[PaymentGateway, Depends(get_payment_gateway)]


def _initiation_read(result: PaymentInitiation) -> PagoRead:
    return PagoRead.model_validate(result.payment).model_copy(
        update={
            "client_secret": result.session.client_secret,
            "publishable_key": result.publishable_key,
            "moneda": result.currency.upper(),
        }
    )


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
    gateway: GatewayDependency,
) -> PagoRead:
    return _initiation_read(
        PaymentService(db, gateway=gateway).initiate(
            order_id, customer=current_user
        )
    )


@router.post("/stripe/webhook", response_model=StripeWebhookRead)
async def stripe_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    gateway: GatewayDependency,
    stripe_signature: Annotated[
        str | None, Header(alias="Stripe-Signature")
    ] = None,
) -> StripeWebhookRead:
    result = PaymentService(db, gateway=gateway).handle_webhook(
        payload=await request.body(), signature=stripe_signature
    )
    return StripeWebhookRead(
        recibido=result.received,
        procesado=result.processed,
        evento_id=result.event_id,
    )


@router.post("/{payment_id}/confirm", response_model=PagoRead)
def confirm_payment(
    payment_id: UUID,
    data: ConfirmacionPagoPruebaRequest,
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
    gateway: GatewayDependency,
) -> PagoRead:
    return PagoRead.model_validate(
        PaymentService(db, gateway=gateway).confirm(
            payment_id,
            approve=data.resultado_prueba == "APROBAR",
            customer=current_user,
        )
    )
