"""Casos de uso básicos de proveedores."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.suppliers.models import Proveedor
from app.modules.suppliers.repository import SupplierRepository
from app.modules.suppliers.schemas import ProveedorCreate, ProveedorUpdate


class SupplierService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.suppliers = SupplierRepository(db)

    def list(
        self, *, page: int, page_size: int, query: str | None, active: bool | None
    ) -> tuple[list[Proveedor], int]:
        return self.suppliers.list(
            offset=(page - 1) * page_size, limit=page_size, query=query, active=active
        )

    def get(self, supplier_id: UUID) -> Proveedor:
        supplier = self.suppliers.get_by_id(supplier_id)
        if supplier is None:
            raise NotFoundError("Proveedor no encontrado.")
        return supplier

    def create(self, data: ProveedorCreate) -> Proveedor:
        self._validate_uniques(data.nombre, data.nit)
        values = data.model_dump()
        if values["email"] is not None:
            values["email"] = str(values["email"]).lower()
        supplier = Proveedor(**values)
        self.suppliers.add(supplier)
        return self._commit(supplier)

    def update(self, supplier_id: UUID, data: ProveedorUpdate) -> Proveedor:
        supplier = self.get(supplier_id)
        target_name = data.nombre if "nombre" in data.model_fields_set and data.nombre else supplier.nombre
        target_nit = data.nit if "nit" in data.model_fields_set else supplier.nit
        self._validate_uniques(target_name, target_nit, current_id=supplier.id)
        for field in data.model_fields_set:
            value = getattr(data, field)
            if field == "email" and value is not None:
                value = str(value).lower()
            setattr(supplier, field, value)
        return self._commit(supplier)

    def delete(self, supplier_id: UUID) -> None:
        self.suppliers.delete(self.get(supplier_id))
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("El proveedor tiene información relacionada y no puede eliminarse.") from exc

    def _validate_uniques(
        self, name: str, nit: str | None, current_id: UUID | None = None
    ) -> None:
        duplicate_name = self.suppliers.get_by_name(name)
        if duplicate_name and duplicate_name.id != current_id:
            raise ConflictError("Ya existe un proveedor con ese nombre.")
        if nit:
            duplicate_nit = self.suppliers.get_by_nit(nit)
            if duplicate_nit and duplicate_nit.id != current_id:
                raise ConflictError("Ya existe un proveedor con ese NIT.")

    def _commit(self, supplier: Proveedor) -> Proveedor:
        try:
            self.db.commit()
            self.db.refresh(supplier)
            return supplier
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("No se pudo guardar el proveedor.") from exc
