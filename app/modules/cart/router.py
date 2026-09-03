"""Endpoints del carrito de compras."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.cart.schemas import (
    CarritoRead,
    DetalleCarritoCreate,
    DetalleCarritoUpdate,
)
from app.modules.cart.service import CartService
from app.modules.users.models import Usuario


router = APIRouter(prefix="/cart", tags=["cart"])
Customer = Annotated[Usuario, Depends(require_roles("cliente"))]


@router.get("", response_model=CarritoRead)
def get_cart(
    current_user: Customer, db: Annotated[Session, Depends(get_db)]
) -> CarritoRead:
    return CarritoRead.model_validate(CartService(db).get(customer=current_user))


@router.post("/items", response_model=CarritoRead, status_code=status.HTTP_201_CREATED)
def add_cart_item(
    data: DetalleCarritoCreate,
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
) -> CarritoRead:
    return CarritoRead.model_validate(CartService(db).add_item(data, customer=current_user))


@router.patch("/items/{item_id}", response_model=CarritoRead)
def update_cart_item(
    item_id: UUID,
    data: DetalleCarritoUpdate,
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
) -> CarritoRead:
    return CarritoRead.model_validate(
        CartService(db).update_item(item_id, data, customer=current_user)
    )


@router.delete("/items/{item_id}", response_model=CarritoRead)
def remove_cart_item(
    item_id: UUID,
    current_user: Customer,
    db: Annotated[Session, Depends(get_db)],
) -> CarritoRead:
    return CarritoRead.model_validate(CartService(db).remove_item(item_id, customer=current_user))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(
    current_user: Customer, db: Annotated[Session, Depends(get_db)]
) -> Response:
    CartService(db).clear(customer=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
