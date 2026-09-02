"""Persistencia de categorías."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.categories.models import Categoria


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, category_id: UUID) -> Categoria | None:
        return self.db.get(Categoria, category_id)

    def get_by_name(self, name: str) -> Categoria | None:
        return self.db.scalar(
            select(Categoria).where(func.lower(Categoria.nombre) == name.lower())
        )

    def list(
        self, *, offset: int, limit: int, query: str | None, active: bool | None
    ) -> tuple[list[Categoria], int]:
        filters = []
        if query:
            pattern = f"%{query.strip()}%"
            filters.append(
                or_(Categoria.nombre.ilike(pattern), Categoria.descripcion.ilike(pattern))
            )
        if active is not None:
            filters.append(Categoria.activa == active)
        rows = select(Categoria).where(*filters).order_by(Categoria.nombre).offset(offset).limit(limit)
        total = select(func.count()).select_from(Categoria).where(*filters)
        return list(self.db.scalars(rows)), self.db.scalar(total) or 0

    def add(self, category: Categoria) -> None:
        self.db.add(category)

    def delete(self, category: Categoria) -> None:
        self.db.delete(category)
