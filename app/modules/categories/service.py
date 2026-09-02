"""Casos de uso de categorías."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.categories.models import Categoria
from app.modules.categories.repository import CategoryRepository
from app.modules.categories.schemas import CategoriaCreate, CategoriaUpdate


class CategoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.categories = CategoryRepository(db)

    def list(
        self, *, page: int, page_size: int, query: str | None, active: bool | None
    ) -> tuple[list[Categoria], int]:
        return self.categories.list(
            offset=(page - 1) * page_size, limit=page_size, query=query, active=active
        )

    def get(self, category_id: UUID) -> Categoria:
        category = self.categories.get_by_id(category_id)
        if category is None:
            raise NotFoundError("Categoría no encontrada.")
        return category

    def create(self, data: CategoriaCreate) -> Categoria:
        if self.categories.get_by_name(data.nombre):
            raise ConflictError("Ya existe una categoría con ese nombre.")
        category = Categoria(**data.model_dump())
        self.categories.add(category)
        return self._commit(category)

    def update(self, category_id: UUID, data: CategoriaUpdate) -> Categoria:
        category = self.get(category_id)
        if "nombre" in data.model_fields_set and data.nombre is not None:
            duplicate = self.categories.get_by_name(data.nombre)
            if duplicate and duplicate.id != category.id:
                raise ConflictError("Ya existe una categoría con ese nombre.")
        for field in data.model_fields_set:
            setattr(category, field, getattr(data, field))
        return self._commit(category)

    def delete(self, category_id: UUID) -> None:
        self.categories.delete(self.get(category_id))
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("La categoría tiene información relacionada y no puede eliminarse.") from exc

    def _commit(self, category: Categoria) -> Categoria:
        try:
            self.db.commit()
            self.db.refresh(category)
            return category
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("No se pudo guardar la categoría.") from exc
