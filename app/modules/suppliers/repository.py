"""Persistencia de proveedores."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.suppliers.models import Proveedor


class SupplierRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, supplier_id: UUID) -> Proveedor | None:
        return self.db.get(Proveedor, supplier_id)

    def get_by_name(self, name: str) -> Proveedor | None:
        return self.db.scalar(
            select(Proveedor).where(func.lower(Proveedor.nombre) == name.lower())
        )

    def get_by_nit(self, nit: str) -> Proveedor | None:
        return self.db.scalar(select(Proveedor).where(Proveedor.nit == nit))

    def list(
        self, *, offset: int, limit: int, query: str | None, active: bool | None
    ) -> tuple[list[Proveedor], int]:
        filters = []
        if query:
            pattern = f"%{query.strip()}%"
            filters.append(
                or_(
                    Proveedor.nombre.ilike(pattern),
                    Proveedor.nit.ilike(pattern),
                    Proveedor.email.ilike(pattern),
                )
            )
        if active is not None:
            filters.append(Proveedor.activo == active)
        rows = select(Proveedor).where(*filters).order_by(Proveedor.nombre).offset(offset).limit(limit)
        total = select(func.count()).select_from(Proveedor).where(*filters)
        return list(self.db.scalars(rows)), self.db.scalar(total) or 0

    def add(self, supplier: Proveedor) -> None:
        self.db.add(supplier)

    def delete(self, supplier: Proveedor) -> None:
        self.db.delete(supplier)
