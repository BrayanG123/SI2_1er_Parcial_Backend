"""Persistencia de ciudades y sucursales."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.modules.branches.models import Ciudad, Sucursal
from app.modules.users.models import Usuario


class CityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, city_id: UUID) -> Ciudad | None:
        return self.db.get(Ciudad, city_id)

    def get_by_name(self, name: str) -> Ciudad | None:
        return self.db.scalar(select(Ciudad).where(func.lower(Ciudad.nombre) == name.lower()))

    def list(self, *, offset: int, limit: int, query: str | None) -> tuple[list[Ciudad], int]:
        filters = []
        if query:
            pattern = f"%{query.strip()}%"
            filters.append(or_(Ciudad.nombre.ilike(pattern), Ciudad.departamento.ilike(pattern)))
        rows = select(Ciudad).where(*filters).order_by(Ciudad.nombre).offset(offset).limit(limit)
        total = select(func.count()).select_from(Ciudad).where(*filters)
        return list(self.db.scalars(rows)), self.db.scalar(total) or 0

    def add(self, city: Ciudad) -> None:
        self.db.add(city)

    def delete(self, city: Ciudad) -> None:
        self.db.delete(city)

    def branch_count(self, city_id: UUID) -> int:
        statement = select(func.count()).select_from(Sucursal).where(Sucursal.ciudad_id == city_id)
        return self.db.scalar(statement) or 0


class BranchRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, branch_id: UUID) -> Sucursal | None:
        statement = select(Sucursal).where(Sucursal.id == branch_id).options(joinedload(Sucursal.ciudad))
        return self.db.scalar(statement)

    def get_by_name_and_city(self, name: str, city_id: UUID) -> Sucursal | None:
        statement = select(Sucursal).where(
            Sucursal.ciudad_id == city_id,
            func.lower(Sucursal.nombre) == name.lower(),
        )
        return self.db.scalar(statement)

    def list(
        self,
        *,
        offset: int,
        limit: int,
        query: str | None,
        city_id: UUID | None,
        active: bool | None,
    ) -> tuple[list[Sucursal], int]:
        filters = []
        if query:
            pattern = f"%{query.strip()}%"
            filters.append(or_(Sucursal.nombre.ilike(pattern), Sucursal.direccion.ilike(pattern)))
        if city_id is not None:
            filters.append(Sucursal.ciudad_id == city_id)
        if active is not None:
            filters.append(Sucursal.activa == active)
        rows = (
            select(Sucursal)
            .where(*filters)
            .options(joinedload(Sucursal.ciudad))
            .order_by(Sucursal.nombre)
            .offset(offset)
            .limit(limit)
        )
        total = select(func.count()).select_from(Sucursal).where(*filters)
        return list(self.db.scalars(rows)), self.db.scalar(total) or 0

    def add(self, branch: Sucursal) -> None:
        self.db.add(branch)

    def delete(self, branch: Sucursal) -> None:
        self.db.delete(branch)

    def assigned_user_count(self, branch_id: UUID) -> int:
        statement = select(func.count()).select_from(Usuario).where(Usuario.sucursal_id == branch_id)
        return self.db.scalar(statement) or 0
