"""Casos de uso del catálogo."""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.catalog.models import (
    Coleccion, Color, ImagenProducto, Producto, Talla, Temporada, VarianteProducto,
)
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    ColeccionCreate, ColeccionUpdate, ColorCreate, ColorUpdate, ProductoCreate,
    ProductoUpdate, TallaCreate, TallaUpdate, TemporadaCreate, TemporadaUpdate,
    VarianteCreate, VarianteUpdate,
)
from app.modules.categories.models import Categoria
from app.modules.suppliers.models import Proveedor


class CatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.catalog = CatalogRepository(db)

    def list_sizes(self) -> list[Talla]:
        return self.catalog.list_sizes()

    def create_size(self, data: TallaCreate) -> Talla:
        self._ensure_unique_name(Talla, data.nombre, "talla")
        entity = Talla(**data.model_dump())
        self.catalog.add(entity)
        return self._commit(entity, "No se pudo guardar la talla.")

    def update_size(self, entity_id: UUID, data: TallaUpdate) -> Talla:
        entity = self._get(Talla, entity_id, "Talla no encontrada.")
        self._update_named(entity, data, Talla, "talla")
        return self._commit(entity, "No se pudo guardar la talla.")

    def delete_size(self, entity_id: UUID) -> None:
        entity = self._get(Talla, entity_id, "Talla no encontrada.")
        if self.catalog.count(VarianteProducto, VarianteProducto.talla_id == entity.id):
            raise ConflictError("No se puede eliminar una talla utilizada por variantes.")
        self._delete(entity, "No se pudo eliminar la talla.")

    def list_colors(self) -> list[Color]:
        return self.catalog.list_colors()

    def create_color(self, data: ColorCreate) -> Color:
        self._ensure_unique_name(Color, data.nombre, "color")
        entity = Color(**data.model_dump())
        self.catalog.add(entity)
        return self._commit(entity, "No se pudo guardar el color.")

    def update_color(self, entity_id: UUID, data: ColorUpdate) -> Color:
        entity = self._get(Color, entity_id, "Color no encontrado.")
        self._update_named(entity, data, Color, "color")
        return self._commit(entity, "No se pudo guardar el color.")

    def delete_color(self, entity_id: UUID) -> None:
        entity = self._get(Color, entity_id, "Color no encontrado.")
        if self.catalog.count(VarianteProducto, VarianteProducto.color_id == entity.id):
            raise ConflictError("No se puede eliminar un color utilizado por variantes.")
        self._delete(entity, "No se pudo eliminar el color.")

    def list_seasons(self, *, active: bool | None = None) -> list[Temporada]:
        return self.catalog.list_seasons(active=active)

    def create_season(self, data: TemporadaCreate) -> Temporada:
        self._ensure_unique_name(Temporada, data.nombre, "temporada")
        entity = Temporada(**data.model_dump())
        self.catalog.add(entity)
        return self._commit(entity, "No se pudo guardar la temporada.")

    def update_season(self, entity_id: UUID, data: TemporadaUpdate) -> Temporada:
        entity = self._get(Temporada, entity_id, "Temporada no encontrada.")
        start = data.fecha_inicio if "fecha_inicio" in data.model_fields_set else entity.fecha_inicio
        end = data.fecha_fin if "fecha_fin" in data.model_fields_set else entity.fecha_fin
        if start and end and start > end:
            raise ConflictError("La fecha inicial no puede ser posterior a la fecha final.")
        self._update_named(entity, data, Temporada, "temporada")
        return self._commit(entity, "No se pudo guardar la temporada.")

    def delete_season(self, entity_id: UUID) -> None:
        entity = self._get(Temporada, entity_id, "Temporada no encontrada.")
        if self.catalog.count(Coleccion, Coleccion.temporada_id == entity.id):
            raise ConflictError("No se puede eliminar una temporada con colecciones.")
        if self.catalog.count(Producto, Producto.temporada_id == entity.id):
            raise ConflictError("No se puede eliminar una temporada utilizada por productos.")
        self._delete(entity, "No se pudo eliminar la temporada.")

    def list_collections(
        self, *, season_id: UUID | None = None, public: bool = False
    ) -> list[Coleccion]:
        return self.catalog.list_collections(season_id=season_id, public=public)

    def create_collection(self, data: ColeccionCreate) -> Coleccion:
        self._get(Temporada, data.temporada_id, "Temporada no encontrada.")
        if self.catalog.get_collection_by_name(data.nombre, data.temporada_id):
            raise ConflictError("Ya existe una colección con ese nombre en la temporada.")
        entity = Coleccion(**data.model_dump())
        self.catalog.add(entity)
        return self._commit_and_reload_collection(entity)

    def update_collection(self, entity_id: UUID, data: ColeccionUpdate) -> Coleccion:
        entity = self._get(Coleccion, entity_id, "Colección no encontrada.")
        target_season = data.temporada_id or entity.temporada_id
        target_name = data.nombre.strip() if data.nombre else entity.nombre
        self._get(Temporada, target_season, "Temporada no encontrada.")
        duplicate = self.catalog.get_collection_by_name(target_name, target_season)
        if duplicate and duplicate.id != entity.id:
            raise ConflictError("Ya existe una colección con ese nombre en la temporada.")
        for field in data.model_fields_set:
            value = getattr(data, field)
            if field in {"nombre", "descripcion"}:
                value = value.strip() or None if value else None
            if field == "temporada_id" and value is None:
                continue
            setattr(entity, field, value)
        return self._commit_and_reload_collection(entity)

    def delete_collection(self, entity_id: UUID) -> None:
        entity = self._get(Coleccion, entity_id, "Colección no encontrada.")
        if self.catalog.count(Producto, Producto.coleccion_id == entity.id):
            raise ConflictError("No se puede eliminar una colección utilizada por productos.")
        self._delete(entity, "No se pudo eliminar la colección.")

    def list_products(
        self,
        *,
        page: int,
        page_size: int,
        query: str | None,
        category_id: UUID | None,
        season_id: UUID | None,
        size_id: UUID | None,
        color_id: UUID | None,
        public: bool,
    ) -> tuple[list[Producto], int]:
        return self.catalog.list_products(
            offset=(page - 1) * page_size,
            limit=page_size,
            query=query,
            category_id=category_id,
            season_id=season_id,
            size_id=size_id,
            color_id=color_id,
            public=public,
        )

    def get_product(self, product_id: UUID, *, public: bool = False) -> Producto:
        product = self.catalog.get_product(product_id, public=public)
        if product is None:
            raise NotFoundError("Producto no encontrado.")
        return product

    def create_product(self, data: ProductoCreate) -> Producto:
        self._validate_product_relations(
            data.categoria_id, data.proveedor_id, data.temporada_id, data.coleccion_id
        )
        variants = []
        for item in data.variantes:
            self._validate_variant_references(item.talla_id, item.color_id)
            if self.catalog.get_variant_by_sku(item.sku):
                raise ConflictError(f"Ya existe una variante con el SKU {item.sku}.")
            variants.append(VarianteProducto(**item.model_dump()))
        product_values = data.model_dump(exclude={"variantes", "imagenes"})
        product = Producto(
            **product_values,
            variantes=variants,
            imagenes=self._build_images(data.imagenes),
        )
        self.catalog.add(product)
        return self._commit_product(product)

    def update_product(self, product_id: UUID, data: ProductoUpdate) -> Producto:
        product = self.get_product(product_id)
        fields = data.model_fields_set
        category_id = data.categoria_id if "categoria_id" in fields and data.categoria_id else product.categoria_id
        supplier_id = data.proveedor_id if "proveedor_id" in fields and data.proveedor_id else product.proveedor_id
        season_id = data.temporada_id if "temporada_id" in fields else product.temporada_id
        collection_id = data.coleccion_id if "coleccion_id" in fields else product.coleccion_id
        self._validate_product_relations(category_id, supplier_id, season_id, collection_id)
        for field in fields - {"imagenes"}:
            value = getattr(data, field)
            if field in {"nombre", "descripcion", "marca"}:
                value = value.strip() or None if value else None
            if field in {"categoria_id", "proveedor_id"} and value is None:
                continue
            setattr(product, field, value)
        if "imagenes" in fields and data.imagenes is not None:
            product.imagenes = self._build_images(data.imagenes)
        return self._commit_product(product)

    def delete_product(self, product_id: UUID) -> None:
        self.catalog.delete(self.get_product(product_id))
        self._commit_delete("El producto tiene información relacionada y no puede eliminarse.")

    def create_variant(self, product_id: UUID, data: VarianteCreate) -> VarianteProducto:
        self.get_product(product_id)
        self._validate_variant_references(data.talla_id, data.color_id)
        self._validate_variant_uniques(product_id, data.talla_id, data.color_id, data.sku)
        variant = VarianteProducto(producto_id=product_id, **data.model_dump())
        self.catalog.add(variant)
        self._commit(variant, "No se pudo guardar la variante.")
        return self.catalog.get_variant(variant.id)  # type: ignore[return-value]

    def update_variant(self, variant_id: UUID, data: VarianteUpdate) -> VarianteProducto:
        variant = self._get(VarianteProducto, variant_id, "Variante no encontrada.")
        fields = data.model_fields_set
        size_id = data.talla_id if "talla_id" in fields and data.talla_id else variant.talla_id
        color_id = data.color_id if "color_id" in fields and data.color_id else variant.color_id
        sku = data.sku if "sku" in fields and data.sku else variant.sku
        self._validate_variant_references(size_id, color_id)
        self._validate_variant_uniques(variant.producto_id, size_id, color_id, sku, variant.id)
        for field in fields:
            value = getattr(data, field)
            if field in {"talla_id", "color_id", "sku"} and value is None:
                continue
            setattr(variant, field, value)
        self._commit(variant, "No se pudo guardar la variante.")
        return self.catalog.get_variant(variant.id)  # type: ignore[return-value]

    def delete_variant(self, variant_id: UUID) -> None:
        variant = self._get(VarianteProducto, variant_id, "Variante no encontrada.")
        if self.catalog.variant_count(variant.producto_id) <= 1:
            raise ConflictError("Un producto debe conservar al menos una variante.")
        self.catalog.delete(variant)
        self._commit_delete("La variante tiene información relacionada y no puede eliminarse.")

    def _validate_product_relations(
        self,
        category_id: UUID,
        supplier_id: UUID,
        season_id: UUID | None,
        collection_id: UUID | None,
    ) -> None:
        category = self._get(Categoria, category_id, "Categoría no encontrada.")
        supplier = self._get(Proveedor, supplier_id, "Proveedor no encontrado.")
        if not category.activa or not supplier.activo:
            raise ConflictError("La categoría y el proveedor deben estar activos.")
        season = None
        if season_id:
            season = self._get(Temporada, season_id, "Temporada no encontrada.")
        if collection_id:
            collection = self._get(Coleccion, collection_id, "Colección no encontrada.")
            if season is None or collection.temporada_id != season.id:
                raise ConflictError("La colección debe pertenecer a la temporada del producto.")

    def _validate_variant_references(self, size_id: UUID, color_id: UUID) -> None:
        self._get(Talla, size_id, "Talla no encontrada.")
        self._get(Color, color_id, "Color no encontrado.")

    def _validate_variant_uniques(
        self,
        product_id: UUID,
        size_id: UUID,
        color_id: UUID,
        sku: str,
        current_id: UUID | None = None,
    ) -> None:
        by_sku = self.catalog.get_variant_by_sku(sku)
        if by_sku and by_sku.id != current_id:
            raise ConflictError("Ya existe una variante con ese SKU.")
        by_combination = self.catalog.get_variant_by_combination(product_id, size_id, color_id)
        if by_combination and by_combination.id != current_id:
            raise ConflictError("Ya existe esa combinación de talla y color para el producto.")

    def _ensure_unique_name(
        self, model: type[Any], name: str, label: str, current_id: UUID | None = None
    ) -> None:
        duplicate = self.catalog.get_by_name(model, name)
        if duplicate and duplicate.id != current_id:
            raise ConflictError(f"Ya existe un {label} con ese nombre.")

    def _update_named(self, entity: Any, data: Any, model: type[Any], label: str) -> None:
        if "nombre" in data.model_fields_set and data.nombre is not None:
            self._ensure_unique_name(model, data.nombre, label, entity.id)
        for field in data.model_fields_set:
            setattr(entity, field, getattr(data, field))

    def _get(self, model: type[Any], entity_id: UUID, message: str) -> Any:
        entity = self.catalog.get(model, entity_id)
        if entity is None:
            raise NotFoundError(message)
        return entity

    @staticmethod
    def _build_images(items: list[Any]) -> list[ImagenProducto]:
        images = [
            ImagenProducto(
                url=str(item.url), es_principal=item.es_principal, orden=item.orden
            )
            for item in items
        ]
        if images and not any(image.es_principal for image in images):
            images[0].es_principal = True
        return images

    def _commit_and_reload_collection(self, entity: Coleccion) -> Coleccion:
        self._commit(entity, "No se pudo guardar la colección.")
        return self.catalog.get(Coleccion, entity.id)  # type: ignore[return-value]

    def _commit_product(self, product: Producto) -> Producto:
        self._commit(product, "No se pudo guardar el producto o sus variantes.")
        return self.get_product(product.id)

    def _commit(self, entity: Any, message: str) -> Any:
        try:
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(message) from exc

    def _delete(self, entity: Any, message: str) -> None:
        self.catalog.delete(entity)
        self._commit_delete(message)

    def _commit_delete(self, message: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(message) from exc
