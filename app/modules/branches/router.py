"""Endpoints administrativos de ciudades y sucursales."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser
from app.modules.branches.schemas import (
    CiudadCreate,
    CiudadPage,
    CiudadRead,
    CiudadUpdate,
    SucursalCreate,
    SucursalPage,
    SucursalRead,
    SucursalUpdate,
)
from app.modules.branches.service import BranchService, CityService


cities_router = APIRouter(prefix="/cities", tags=["cities"])
branches_router = APIRouter(prefix="/branches", tags=["branches"])


@cities_router.get("", response_model=CiudadPage)
def list_cities(
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(max_length=120)] = None,
) -> CiudadPage:
    cities, total = CityService(db).list(page=page, page_size=page_size, query=q)
    return CiudadPage(items=cities, page=page, page_size=page_size, total=total)


@cities_router.post("", response_model=CiudadRead, status_code=status.HTTP_201_CREATED)
def create_city(data: CiudadCreate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> CiudadRead:
    return CiudadRead.model_validate(CityService(db).create(data))


@cities_router.get("/{city_id}", response_model=CiudadRead)
def get_city(city_id: UUID, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> CiudadRead:
    return CiudadRead.model_validate(CityService(db).get(city_id))


@cities_router.patch("/{city_id}", response_model=CiudadRead)
def update_city(city_id: UUID, data: CiudadUpdate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> CiudadRead:
    return CiudadRead.model_validate(CityService(db).update(city_id, data))


@cities_router.delete("/{city_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_city(city_id: UUID, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> Response:
    CityService(db).delete(city_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@branches_router.get("", response_model=SucursalPage)
def list_branches(
    _admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(max_length=120)] = None,
    city_id: UUID | None = None,
    active: bool | None = None,
) -> SucursalPage:
    branches, total = BranchService(db).list(
        page=page, page_size=page_size, query=q, city_id=city_id, active=active
    )
    return SucursalPage(items=branches, page=page, page_size=page_size, total=total)


@branches_router.post("", response_model=SucursalRead, status_code=status.HTTP_201_CREATED)
def create_branch(data: SucursalCreate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> SucursalRead:
    return SucursalRead.model_validate(BranchService(db).create(data))


@branches_router.get("/{branch_id}", response_model=SucursalRead)
def get_branch(branch_id: UUID, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> SucursalRead:
    return SucursalRead.model_validate(BranchService(db).get(branch_id))


@branches_router.patch("/{branch_id}", response_model=SucursalRead)
def update_branch(branch_id: UUID, data: SucursalUpdate, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> SucursalRead:
    return SucursalRead.model_validate(BranchService(db).update(branch_id, data))


@branches_router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_branch(branch_id: UUID, _admin: AdminUser, db: Annotated[Session, Depends(get_db)]) -> Response:
    BranchService(db).delete(branch_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
