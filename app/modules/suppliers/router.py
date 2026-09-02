"""Endpoints CRUD administrativos de proveedores."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser
from app.modules.suppliers.schemas import (
    ProveedorCreate, ProveedorPage, ProveedorRead, ProveedorUpdate,
)
from app.modules.suppliers.service import SupplierService


router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("", response_model=ProveedorPage)
def list_suppliers(
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(max_length=160)] = None,
    active: bool | None = None,
) -> ProveedorPage:
    items, total = SupplierService(db).list(
        page=page, page_size=page_size, query=q, active=active
    )
    return ProveedorPage(items=items, page=page, page_size=page_size, total=total)


@router.post("", response_model=ProveedorRead, status_code=status.HTTP_201_CREATED)
def create_supplier(
    data: ProveedorCreate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]
) -> ProveedorRead:
    return ProveedorRead.model_validate(SupplierService(db).create(data))


@router.get("/{supplier_id}", response_model=ProveedorRead)
def get_supplier(
    supplier_id: UUID, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]
) -> ProveedorRead:
    return ProveedorRead.model_validate(SupplierService(db).get(supplier_id))


@router.patch("/{supplier_id}", response_model=ProveedorRead)
def update_supplier(
    supplier_id: UUID,
    data: ProveedorUpdate,
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> ProveedorRead:
    return ProveedorRead.model_validate(SupplierService(db).update(supplier_id, data))


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(
    supplier_id: UUID, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]
) -> Response:
    SupplierService(db).delete(supplier_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
