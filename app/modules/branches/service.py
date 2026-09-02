"""Casos de uso de ciudades y sucursales."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.branches.models import Ciudad, Sucursal
from app.modules.branches.repository import BranchRepository, CityRepository
from app.modules.branches.schemas import CiudadCreate, CiudadUpdate, SucursalCreate, SucursalUpdate


class CityService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.cities = CityRepository(db)

    def list(self, *, page: int, page_size: int, query: str | None) -> tuple[list[Ciudad], int]:
        return self.cities.list(offset=(page - 1) * page_size, limit=page_size, query=query)

    def get(self, city_id: UUID) -> Ciudad:
        city = self.cities.get_by_id(city_id)
        if city is None:
            raise NotFoundError("Ciudad no encontrada.")
        return city

    def create(self, data: CiudadCreate) -> Ciudad:
        if self.cities.get_by_name(data.nombre):
            raise ConflictError("Ya existe una ciudad con ese nombre.")
        city = Ciudad(nombre=data.nombre, departamento=data.departamento)
        self.cities.add(city)
        return self._commit(city)

    def update(self, city_id: UUID, data: CiudadUpdate) -> Ciudad:
        city = self.get(city_id)
        if "nombre" in data.model_fields_set and data.nombre is not None:
            name = data.nombre.strip()
            duplicate = self.cities.get_by_name(name)
            if duplicate and duplicate.id != city.id:
                raise ConflictError("Ya existe una ciudad con ese nombre.")
            city.nombre = name
        if "departamento" in data.model_fields_set:
            city.departamento = data.departamento.strip() or None if data.departamento else None
        return self._commit(city)

    def delete(self, city_id: UUID) -> None:
        city = self.get(city_id)
        if self.cities.branch_count(city.id):
            raise ConflictError("No se puede eliminar una ciudad que tiene sucursales.")
        self.cities.delete(city)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("No se pudo eliminar la ciudad.") from exc

    def _commit(self, city: Ciudad) -> Ciudad:
        try:
            self.db.commit()
            self.db.refresh(city)
            return city
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("No se pudo guardar la ciudad.") from exc


class BranchService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.branches = BranchRepository(db)
        self.cities = CityRepository(db)

    def list(
        self,
        *,
        page: int,
        page_size: int,
        query: str | None,
        city_id: UUID | None,
        active: bool | None,
    ) -> tuple[list[Sucursal], int]:
        return self.branches.list(
            offset=(page - 1) * page_size,
            limit=page_size,
            query=query,
            city_id=city_id,
            active=active,
        )

    def get(self, branch_id: UUID) -> Sucursal:
        branch = self.branches.get_by_id(branch_id)
        if branch is None:
            raise NotFoundError("Sucursal no encontrada.")
        return branch

    def create(self, data: SucursalCreate) -> Sucursal:
        self._ensure_city(data.ciudad_id)
        if self.branches.get_by_name_and_city(data.nombre, data.ciudad_id):
            raise ConflictError("Ya existe una sucursal con ese nombre en la ciudad.")
        branch = Sucursal(**data.model_dump())
        self.branches.add(branch)
        return self._commit(branch)

    def update(self, branch_id: UUID, data: SucursalUpdate) -> Sucursal:
        branch = self.get(branch_id)
        fields = data.model_fields_set
        target_city = data.ciudad_id if "ciudad_id" in fields and data.ciudad_id else branch.ciudad_id
        target_name = data.nombre.strip() if "nombre" in fields and data.nombre else branch.nombre
        if "ciudad_id" in fields and data.ciudad_id is not None:
            self._ensure_city(data.ciudad_id)
        duplicate = self.branches.get_by_name_and_city(target_name, target_city)
        if duplicate and duplicate.id != branch.id:
            raise ConflictError("Ya existe una sucursal con ese nombre en la ciudad.")
        for field in fields:
            value = getattr(data, field)
            if field in {"nombre", "direccion", "horario_informativo"} and value is not None:
                value = value.strip()
            if field == "telefono":
                value = value.strip() or None if value else None
            if field == "ciudad_id" and value is None:
                continue
            setattr(branch, field, value)
        return self._commit(branch)

    def delete(self, branch_id: UUID) -> None:
        branch = self.get(branch_id)
        if self.branches.assigned_user_count(branch.id):
            raise ConflictError("No se puede eliminar una sucursal con empleados asignados.")
        self.branches.delete(branch)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("La sucursal tiene información relacionada y no puede eliminarse.") from exc

    def _ensure_city(self, city_id: UUID) -> None:
        if self.cities.get_by_id(city_id) is None:
            raise NotFoundError("Ciudad no encontrada.")

    def _commit(self, branch: Sucursal) -> Sucursal:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("No se pudo guardar la sucursal.") from exc
        return self.get(branch.id)
