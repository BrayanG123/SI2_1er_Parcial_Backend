"""Endpoints de consulta y movimiento de inventario."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import InventoryManager, InventoryReader
from app.modules.inventory.schemas import (
    AjusteCreate,
    DisponibilidadSucursalRead,
    EstadoStock,
    InventarioOptions,
    InventarioPage,
    InventarioRead,
    MovimientoPage,
    RecepcionCreate,
)
from app.modules.inventory.service import InventoryService


router = APIRouter(prefix="/inventory", tags=["inventory"])
public_router = APIRouter(prefix="/catalog/products", tags=["catalog"])


@public_router.get(
    "/{product_id}/availability",
    response_model=list[DisponibilidadSucursalRead],
)
def public_product_availability(
    product_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[DisponibilidadSucursalRead]:
    rows = InventoryService(db).public_availability(product_id)
    return [
        DisponibilidadSucursalRead(
            sucursal_id=item.sucursal_id,
            sucursal_nombre=item.sucursal.nombre,
            ciudad_nombre=item.sucursal.ciudad.nombre,
            variante_id=item.variante_id,
            talla=item.variante.talla.nombre,
            color=item.variante.color.nombre,
            sku=item.variante.sku,
            stock_disponible=item.stock_disponible,
        )
        for item in rows
    ]


@router.get("/options", response_model=InventarioOptions)
def inventory_options(
    current_user: InventoryReader,
    db: Annotated[Session, Depends(get_db)],
) -> InventarioOptions:
    branches, products = InventoryService(db).options(user=current_user)
    return InventarioOptions(sucursales=branches, productos=products)


@router.get("", response_model=InventarioPage)
def list_inventory(
    current_user: InventoryReader,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    branch_id: UUID | None = None,
    city_id: UUID | None = None,
    product_id: UUID | None = None,
    variant_id: UUID | None = None,
    state: EstadoStock | None = None,
) -> InventarioPage:
    items, total = InventoryService(db).list_inventory(
        user=current_user,
        page=page,
        page_size=page_size,
        branch_id=branch_id,
        city_id=city_id,
        product_id=product_id,
        variant_id=variant_id,
        state=state,
    )
    return InventarioPage(items=items, page=page, page_size=page_size, total=total)


@router.post("/receipts", response_model=InventarioRead, status_code=status.HTTP_201_CREATED)
def receive_inventory(
    data: RecepcionCreate,
    current_user: InventoryManager,
    db: Annotated[Session, Depends(get_db)],
) -> InventarioRead:
    return InventarioRead.model_validate(InventoryService(db).receive(data, user=current_user))


@router.post("/adjustments", response_model=InventarioRead)
def adjust_inventory(
    data: AjusteCreate,
    current_user: InventoryManager,
    db: Annotated[Session, Depends(get_db)],
) -> InventarioRead:
    return InventarioRead.model_validate(InventoryService(db).adjust(data, user=current_user))


@router.get("/{inventory_id}", response_model=InventarioRead)
def get_inventory(
    inventory_id: UUID,
    current_user: InventoryReader,
    db: Annotated[Session, Depends(get_db)],
) -> InventarioRead:
    return InventarioRead.model_validate(
        InventoryService(db).get_inventory(inventory_id, user=current_user)
    )


@router.get("/{inventory_id}/movements", response_model=MovimientoPage)
def list_inventory_movements(
    inventory_id: UUID,
    current_user: InventoryReader,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MovimientoPage:
    items, total = InventoryService(db).list_movements(
        inventory_id, user=current_user, page=page, page_size=page_size
    )
    return MovimientoPage(items=items, page=page, page_size=page_size, total=total)
