"""Endpoints administrativos de categorías."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser
from app.modules.categories.schemas import (
    CategoriaCreate, CategoriaPage, CategoriaRead, CategoriaUpdate,
)
from app.modules.categories.service import CategoryService


router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=CategoriaPage)
def list_categories(
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(max_length=120)] = None,
    active: bool | None = None,
) -> CategoriaPage:
    items, total = CategoryService(db).list(
        page=page, page_size=page_size, query=q, active=active
    )
    return CategoriaPage(items=items, page=page, page_size=page_size, total=total)


@router.post("", response_model=CategoriaRead, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoriaCreate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]
) -> CategoriaRead:
    return CategoriaRead.model_validate(CategoryService(db).create(data))


@router.get("/{category_id}", response_model=CategoriaRead)
def get_category(
    category_id: UUID, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]
) -> CategoriaRead:
    return CategoriaRead.model_validate(CategoryService(db).get(category_id))


@router.patch("/{category_id}", response_model=CategoriaRead)
def update_category(
    category_id: UUID,
    data: CategoriaUpdate,
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> CategoriaRead:
    return CategoriaRead.model_validate(CategoryService(db).update(category_id, data))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: UUID, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]
) -> Response:
    CategoryService(db).delete(category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
