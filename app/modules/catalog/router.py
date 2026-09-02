"""Endpoints públicos y administrativos del catálogo."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser
from app.modules.catalog.schemas import (
    ColeccionCreate, ColeccionRead, ColeccionUpdate, ColorCreate, ColorRead,
    ColorUpdate, ProductoCreate, ProductoPage, ProductoRead, ProductoUpdate,
    TallaCreate, TallaRead, TallaUpdate, TemporadaCreate, TemporadaRead,
    TemporadaUpdate, VarianteCreate, VarianteRead, VarianteUpdate,
)
from app.modules.catalog.service import CatalogService
from app.modules.categories.repository import CategoryRepository
from app.modules.categories.schemas import CategoriaRead


public_router = APIRouter(prefix="/catalog", tags=["catalog"])
admin_router = APIRouter(prefix="/admin/catalog", tags=["catalog-admin"])


@public_router.get("/categories", response_model=list[CategoriaRead])
def public_categories(db: Annotated[Session, Depends(get_db)]) -> list[CategoriaRead]:
    items, _ = CategoryRepository(db).list(offset=0, limit=100, query=None, active=True)
    return [CategoriaRead.model_validate(item) for item in items]


@public_router.get("/sizes", response_model=list[TallaRead])
def public_sizes(db: Annotated[Session, Depends(get_db)]) -> list[TallaRead]:
    return [TallaRead.model_validate(item) for item in CatalogService(db).list_sizes()]


@public_router.get("/colors", response_model=list[ColorRead])
def public_colors(db: Annotated[Session, Depends(get_db)]) -> list[ColorRead]:
    return [ColorRead.model_validate(item) for item in CatalogService(db).list_colors()]


@public_router.get("/seasons", response_model=list[TemporadaRead])
def public_seasons(db: Annotated[Session, Depends(get_db)]) -> list[TemporadaRead]:
    return [
        TemporadaRead.model_validate(item)
        for item in CatalogService(db).list_seasons(active=True)
    ]


@public_router.get("/collections", response_model=list[ColeccionRead])
def public_collections(
    db: Annotated[Session, Depends(get_db)], season_id: UUID | None = None
) -> list[ColeccionRead]:
    return [
        ColeccionRead.model_validate(item)
        for item in CatalogService(db).list_collections(season_id=season_id, public=True)
    ]


@public_router.get("/products", response_model=ProductoPage)
def public_products(
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(max_length=180)] = None,
    category_id: UUID | None = None,
    season_id: UUID | None = None,
    size_id: UUID | None = None,
    color_id: UUID | None = None,
) -> ProductoPage:
    items, total = CatalogService(db).list_products(
        page=page, page_size=page_size, query=q, category_id=category_id,
        season_id=season_id, size_id=size_id, color_id=color_id, public=True,
    )
    return ProductoPage(items=items, page=page, page_size=page_size, total=total)


@public_router.get("/products/{product_id}", response_model=ProductoRead)
def public_product(product_id: UUID, db: Annotated[Session, Depends(get_db)]) -> ProductoRead:
    return ProductoRead.model_validate(CatalogService(db).get_product(product_id, public=True))


@admin_router.get("/sizes", response_model=list[TallaRead])
def list_sizes(_admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> list[TallaRead]:
    return [TallaRead.model_validate(item) for item in CatalogService(db).list_sizes()]


@admin_router.post("/sizes", response_model=TallaRead, status_code=status.HTTP_201_CREATED)
def create_size(data: TallaCreate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> TallaRead:
    return TallaRead.model_validate(CatalogService(db).create_size(data))


@admin_router.patch("/sizes/{entity_id}", response_model=TallaRead)
def update_size(entity_id: UUID, data: TallaUpdate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> TallaRead:
    return TallaRead.model_validate(CatalogService(db).update_size(entity_id, data))


@admin_router.delete("/sizes/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_size(entity_id: UUID, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> Response:
    CatalogService(db).delete_size(entity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.get("/colors", response_model=list[ColorRead])
def list_colors(_admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> list[ColorRead]:
    return [ColorRead.model_validate(item) for item in CatalogService(db).list_colors()]


@admin_router.post("/colors", response_model=ColorRead, status_code=status.HTTP_201_CREATED)
def create_color(data: ColorCreate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> ColorRead:
    return ColorRead.model_validate(CatalogService(db).create_color(data))


@admin_router.patch("/colors/{entity_id}", response_model=ColorRead)
def update_color(entity_id: UUID, data: ColorUpdate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> ColorRead:
    return ColorRead.model_validate(CatalogService(db).update_color(entity_id, data))


@admin_router.delete("/colors/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_color(entity_id: UUID, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> Response:
    CatalogService(db).delete_color(entity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.get("/seasons", response_model=list[TemporadaRead])
def list_seasons(_admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> list[TemporadaRead]:
    return [TemporadaRead.model_validate(item) for item in CatalogService(db).list_seasons()]


@admin_router.post("/seasons", response_model=TemporadaRead, status_code=status.HTTP_201_CREATED)
def create_season(data: TemporadaCreate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> TemporadaRead:
    return TemporadaRead.model_validate(CatalogService(db).create_season(data))


@admin_router.patch("/seasons/{entity_id}", response_model=TemporadaRead)
def update_season(entity_id: UUID, data: TemporadaUpdate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> TemporadaRead:
    return TemporadaRead.model_validate(CatalogService(db).update_season(entity_id, data))


@admin_router.delete("/seasons/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_season(entity_id: UUID, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> Response:
    CatalogService(db).delete_season(entity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.get("/collections", response_model=list[ColeccionRead])
def list_collections(
    _admin: AdminUser, db: Annotated[Session, Depends(get_db)], season_id: UUID | None = None
) -> list[ColeccionRead]:
    return [ColeccionRead.model_validate(item) for item in CatalogService(db).list_collections(season_id=season_id)]


@admin_router.post("/collections", response_model=ColeccionRead, status_code=status.HTTP_201_CREATED)
def create_collection(data: ColeccionCreate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> ColeccionRead:
    return ColeccionRead.model_validate(CatalogService(db).create_collection(data))


@admin_router.patch("/collections/{entity_id}", response_model=ColeccionRead)
def update_collection(entity_id: UUID, data: ColeccionUpdate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> ColeccionRead:
    return ColeccionRead.model_validate(CatalogService(db).update_collection(entity_id, data))


@admin_router.delete("/collections/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(entity_id: UUID, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> Response:
    CatalogService(db).delete_collection(entity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.get("/products", response_model=ProductoPage)
def list_products(
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(max_length=180)] = None,
) -> ProductoPage:
    items, total = CatalogService(db).list_products(
        page=page, page_size=page_size, query=q, category_id=None,
        season_id=None, size_id=None, color_id=None, public=False,
    )
    return ProductoPage(items=items, page=page, page_size=page_size, total=total)


@admin_router.post("/products", response_model=ProductoRead, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductoCreate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> ProductoRead:
    return ProductoRead.model_validate(CatalogService(db).create_product(data))


@admin_router.get("/products/{product_id}", response_model=ProductoRead)
def get_product(product_id: UUID, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> ProductoRead:
    return ProductoRead.model_validate(CatalogService(db).get_product(product_id))


@admin_router.patch("/products/{product_id}", response_model=ProductoRead)
def update_product(product_id: UUID, data: ProductoUpdate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> ProductoRead:
    return ProductoRead.model_validate(CatalogService(db).update_product(product_id, data))


@admin_router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: UUID, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> Response:
    CatalogService(db).delete_product(product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.post("/products/{product_id}/variants", response_model=VarianteRead, status_code=status.HTTP_201_CREATED)
def create_variant(product_id: UUID, data: VarianteCreate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> VarianteRead:
    return VarianteRead.model_validate(CatalogService(db).create_variant(product_id, data))


@admin_router.patch("/variants/{variant_id}", response_model=VarianteRead)
def update_variant(variant_id: UUID, data: VarianteUpdate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> VarianteRead:
    return VarianteRead.model_validate(CatalogService(db).update_variant(variant_id, data))


@admin_router.delete("/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variant(variant_id: UUID, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> Response:
    CatalogService(db).delete_variant(variant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
