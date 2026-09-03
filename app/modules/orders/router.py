"""Endpoints de pedidos y ventas unificadas."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import CurrentUser, require_roles
from app.modules.orders.models import CanalPedido, EstadoPedido
from app.modules.orders.schemas import (
    CheckoutCarritoRequest,
    CheckoutReservaRequest,
    PedidoOptions,
    PedidoPage,
    PedidoRead,
    VentaPosRequest,
    VariantePosRead,
)
from app.modules.orders.service import OrderService
from app.modules.users.models import Usuario


router = APIRouter(prefix="/orders", tags=["orders"])
Customer = Annotated[Usuario, Depends(require_roles("cliente"))]
OrderReader = Annotated[
    Usuario, Depends(require_roles("administrador", "encargado", "cajero"))
]
PosSeller = Annotated[Usuario, Depends(require_roles("administrador", "cajero"))]


@router.get("/options", response_model=PedidoOptions)
def order_options(
    current_user: CurrentUser, db: Annotated[Session, Depends(get_db)]
) -> PedidoOptions:
    return PedidoOptions(sucursales=OrderService(db).options(user=current_user))


@router.post("/checkout", response_model=PedidoRead, status_code=status.HTTP_201_CREATED)
def checkout_cart(
    data: CheckoutCarritoRequest,
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
) -> PedidoRead:
    return PedidoRead.model_validate(
        OrderService(db).checkout_cart(data, customer=current_user)
    )


@router.post(
    "/from-reservation/{reservation_id}",
    response_model=PedidoRead,
    status_code=status.HTTP_201_CREATED,
)
def checkout_reservation(
    reservation_id: UUID,
    data: CheckoutReservaRequest,
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
) -> PedidoRead:
    return PedidoRead.model_validate(
        OrderService(db).checkout_reservation(
            reservation_id, data, customer=current_user
        )
    )


@router.get("/mine", response_model=PedidoPage)
def list_my_orders(
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PedidoPage:
    items, total = OrderService(db).list_mine(
        customer=current_user, page=page, page_size=page_size
    )
    return PedidoPage(items=items, page=page, page_size=page_size, total=total)


@router.get("/mine/{order_id}", response_model=PedidoRead)
def get_my_order(
    order_id: UUID,
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
) -> PedidoRead:
    return PedidoRead.model_validate(
        OrderService(db).get_mine(order_id, customer=current_user)
    )


@router.get("/manage", response_model=PedidoPage)
def list_managed_orders(
    current_user: OrderReader,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    branch_id: UUID | None = None,
    channel: CanalPedido | None = None,
    state: EstadoPedido | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> PedidoPage:
    items, total = OrderService(db).list_manage(
        user=current_user,
        page=page,
        page_size=page_size,
        branch_id=branch_id,
        channel=channel,
        state=state,
        date_from=date_from,
        date_to=date_to,
    )
    return PedidoPage(items=items, page=page, page_size=page_size, total=total)


@router.get("/manage/{order_id}", response_model=PedidoRead)
def get_managed_order(
    order_id: UUID,
    current_user: OrderReader,
    db: Annotated[Session, Depends(get_db)],
) -> PedidoRead:
    return PedidoRead.model_validate(
        OrderService(db).get_manage(order_id, user=current_user)
    )


@router.get("/pos/variants", response_model=list[VariantePosRead])
def search_pos_variants(
    current_user: PosSeller,
    db: Annotated[Session, Depends(get_db)],
    sku: Annotated[str, Query(min_length=1, max_length=80)],
    branch_id: UUID | None = None,
) -> list[VariantePosRead]:
    rows = OrderService(db).search_pos(
        user=current_user, sku=sku, branch_id=branch_id
    )
    return [
        VariantePosRead(
            inventario_id=item.id,
            sucursal_id=item.sucursal_id,
            sucursal_nombre=item.sucursal.nombre,
            variante_id=item.variante_id,
            producto_id=item.variante.producto_id,
            producto_nombre=item.variante.producto.nombre,
            sku=item.variante.sku,
            talla=item.variante.talla.nombre,
            color=item.variante.color.nombre,
            precio_unitario=(
                item.variante.precio or item.variante.producto.precio_base
            ),
            stock_disponible=item.stock_disponible,
        )
        for item in rows
    ]


@router.post("/pos", response_model=PedidoRead, status_code=status.HTTP_201_CREATED)
def create_pos_order(
    data: VentaPosRequest,
    current_user: PosSeller,
    db: Annotated[Session, Depends(get_db)],
) -> PedidoRead:
    return PedidoRead.model_validate(
        OrderService(db).create_pos(data, user=current_user)
    )
