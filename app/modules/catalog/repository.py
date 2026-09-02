"""Consultas de productos y variantes."""

from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload, with_loader_criteria

from app.modules.catalog.models import (
    Coleccion, Color, ImagenProducto, Producto, Talla, Temporada, VarianteProducto,
)


class CatalogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, model: type[Any], entity_id: UUID) -> Any | None:
        return self.db.get(model, entity_id)

    def get_by_name(self, model: type[Any], name: str) -> Any | None:
        return self.db.scalar(select(model).where(func.lower(model.nombre) == name.lower()))

    def list_sizes(self) -> list[Talla]:
        return list(self.db.scalars(select(Talla).order_by(Talla.orden.nullslast(), Talla.nombre)))

    def list_colors(self) -> list[Color]:
        return list(self.db.scalars(select(Color).order_by(Color.nombre)))

    def list_seasons(self, *, active: bool | None = None) -> list[Temporada]:
        statement = select(Temporada)
        if active is not None:
            statement = statement.where(Temporada.activa == active)
        return list(self.db.scalars(statement.order_by(Temporada.nombre)))

    def list_collections(
        self, *, season_id: UUID | None = None, public: bool = False
    ) -> list[Coleccion]:
        statement = select(Coleccion)
        if public:
            statement = statement.join(Coleccion.temporada).where(Temporada.activa.is_(True))
        if season_id is not None:
            statement = statement.where(Coleccion.temporada_id == season_id)
        return list(self.db.scalars(statement.order_by(Coleccion.nombre)))

    def get_collection_by_name(self, name: str, season_id: UUID) -> Coleccion | None:
        return self.db.scalar(
            select(Coleccion).where(
                Coleccion.temporada_id == season_id,
                func.lower(Coleccion.nombre) == name.lower(),
            )
        )

    def add(self, entity: Any) -> None:
        self.db.add(entity)

    def delete(self, entity: Any) -> None:
        self.db.delete(entity)

    def count(self, model: type[Any], *conditions: Any) -> int:
        statement = select(func.count()).select_from(model).where(*conditions)
        return self.db.scalar(statement) or 0

    def get_variant(self, variant_id: UUID) -> VarianteProducto | None:
        return self.db.get(VarianteProducto, variant_id)

    def get_variant_by_sku(self, sku: str) -> VarianteProducto | None:
        return self.db.scalar(select(VarianteProducto).where(VarianteProducto.sku == sku))

    def get_variant_by_combination(
        self, product_id: UUID, size_id: UUID, color_id: UUID
    ) -> VarianteProducto | None:
        return self.db.scalar(
            select(VarianteProducto).where(
                VarianteProducto.producto_id == product_id,
                VarianteProducto.talla_id == size_id,
                VarianteProducto.color_id == color_id,
            )
        )

    def variant_count(self, product_id: UUID) -> int:
        statement = select(func.count()).select_from(VarianteProducto).where(
            VarianteProducto.producto_id == product_id
        )
        return self.db.scalar(statement) or 0

    def get_product(self, product_id: UUID, *, public: bool = False) -> Producto | None:
        statement = select(Producto).where(Producto.id == product_id)
        if public:
            statement = statement.where(
                Producto.activo.is_(True),
                Producto.categoria.has(activa=True),
                Producto.proveedor.has(activo=True),
                or_(Producto.temporada_id.is_(None), Producto.temporada.has(activa=True)),
            ).options(
                with_loader_criteria(
                    VarianteProducto, VarianteProducto.activa.is_(True), include_aliases=True
                )
            )
        if public:
            statement = statement.execution_options(populate_existing=True)
        return self.db.scalar(statement.options(*self._product_options()))

    def list_products(
        self,
        *,
        offset: int,
        limit: int,
        query: str | None,
        category_id: UUID | None,
        season_id: UUID | None,
        size_id: UUID | None,
        color_id: UUID | None,
        public: bool,
    ) -> tuple[list[Producto], int]:
        filters = []
        if query:
            pattern = f"%{query.strip()}%"
            filters.append(
                or_(
                    Producto.nombre.ilike(pattern),
                    Producto.descripcion.ilike(pattern),
                    Producto.marca.ilike(pattern),
                )
            )
        if category_id:
            filters.append(Producto.categoria_id == category_id)
        if season_id:
            filters.append(Producto.temporada_id == season_id)
        variant_filters = []
        if size_id:
            variant_filters.append(VarianteProducto.talla_id == size_id)
        if color_id:
            variant_filters.append(VarianteProducto.color_id == color_id)
        if public:
            filters.extend(
                [
                    Producto.activo.is_(True),
                    Producto.categoria.has(activa=True),
                    Producto.proveedor.has(activo=True),
                    or_(Producto.temporada_id.is_(None), Producto.temporada.has(activa=True)),
                    Producto.variantes.any(VarianteProducto.activa.is_(True)),
                ]
            )
            variant_filters.append(VarianteProducto.activa.is_(True))
        if variant_filters and (size_id or color_id):
            filters.append(Producto.variantes.any(and_(*variant_filters)))

        statement = (
            select(Producto)
            .where(*filters)
            .options(*self._product_options())
            .order_by(Producto.nombre)
            .offset(offset)
            .limit(limit)
        )
        if public:
            statement = statement.options(
                with_loader_criteria(
                    VarianteProducto, VarianteProducto.activa.is_(True), include_aliases=True
                )
            ).execution_options(populate_existing=True)
        total_statement = select(func.count()).select_from(Producto).where(*filters)
        return list(self.db.scalars(statement).unique()), self.db.scalar(total_statement) or 0

    @staticmethod
    def _product_options() -> tuple[Any, ...]:
        return (
            selectinload(Producto.variantes).selectinload(VarianteProducto.talla),
            selectinload(Producto.variantes).selectinload(VarianteProducto.color),
            selectinload(Producto.imagenes),
        )
