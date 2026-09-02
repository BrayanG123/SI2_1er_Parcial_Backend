"""Modelos ORM del catálogo."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Talla(Base):
    __tablename__ = "tallas"
    __table_args__ = (
        CheckConstraint("orden IS NULL OR orden >= 0", name="ck_tallas_orden_no_negativo"),
        Index("ix_tallas_nombre", "nombre", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    orden: Mapped[int | None] = mapped_column(Integer)


class Color(Base):
    __tablename__ = "colores"
    __table_args__ = (Index("ix_colores_nombre", "nombre", unique=True),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    codigo_hex: Mapped[str | None] = mapped_column(String(7))


class Temporada(Base):
    __tablename__ = "temporadas"
    __table_args__ = (
        CheckConstraint(
            "fecha_inicio IS NULL OR fecha_fin IS NULL OR fecha_inicio <= fecha_fin",
            name="ck_temporadas_fechas",
        ),
        Index("ix_temporadas_nombre", "nombre", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    fecha_inicio: Mapped[date | None] = mapped_column(Date)
    fecha_fin: Mapped[date | None] = mapped_column(Date)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    colecciones: Mapped[list["Coleccion"]] = relationship(back_populates="temporada", lazy="selectin")


class Coleccion(Base):
    __tablename__ = "colecciones"
    __table_args__ = (
        UniqueConstraint("temporada_id", "nombre", name="uq_colecciones_temporada_nombre"),
        Index("ix_colecciones_temporada_id", "temporada_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    temporada_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("temporadas.id", ondelete="RESTRICT"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(500))
    temporada: Mapped[Temporada] = relationship(back_populates="colecciones", lazy="joined")


class Producto(Base):
    __tablename__ = "productos"
    __table_args__ = (
        CheckConstraint("precio_base > 0", name="ck_productos_precio_positivo"),
        Index("ix_productos_nombre", "nombre"),
        Index("ix_productos_categoria_id", "categoria_id"),
        Index("ix_productos_proveedor_id", "proveedor_id"),
        Index("ix_productos_temporada_id", "temporada_id"),
        Index("ix_productos_coleccion_id", "coleccion_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    categoria_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("categorias.id", ondelete="RESTRICT"), nullable=False
    )
    proveedor_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False
    )
    temporada_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("temporadas.id", ondelete="RESTRICT")
    )
    coleccion_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("colecciones.id", ondelete="RESTRICT")
    )
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(1000))
    marca: Mapped[str | None] = mapped_column(String(120))
    precio_base: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    categoria: Mapped["Categoria"] = relationship(lazy="joined")  # type: ignore[name-defined] # noqa: F821
    proveedor: Mapped["Proveedor"] = relationship(lazy="joined")  # type: ignore[name-defined] # noqa: F821
    temporada: Mapped[Temporada | None] = relationship(lazy="joined")
    coleccion: Mapped[Coleccion | None] = relationship(lazy="joined")
    variantes: Mapped[list["VarianteProducto"]] = relationship(
        back_populates="producto", cascade="all, delete-orphan", lazy="selectin"
    )
    imagenes: Mapped[list["ImagenProducto"]] = relationship(
        back_populates="producto",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ImagenProducto.orden",
    )


class VarianteProducto(Base):
    __tablename__ = "variantes_producto"
    __table_args__ = (
        CheckConstraint("precio IS NULL OR precio > 0", name="ck_variantes_precio_positivo"),
        UniqueConstraint("producto_id", "talla_id", "color_id", name="uq_variantes_producto_talla_color"),
        Index("ix_variantes_sku", "sku", unique=True),
        Index("ix_variantes_producto_id", "producto_id"),
        Index("ix_variantes_talla_id", "talla_id"),
        Index("ix_variantes_color_id", "color_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    producto_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("productos.id", ondelete="CASCADE"), nullable=False
    )
    talla_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tallas.id", ondelete="RESTRICT"), nullable=False
    )
    color_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("colores.id", ondelete="RESTRICT"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    precio: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    producto: Mapped[Producto] = relationship(back_populates="variantes")
    talla: Mapped[Talla] = relationship(lazy="joined")
    color: Mapped[Color] = relationship(lazy="joined")


class ImagenProducto(Base):
    __tablename__ = "imagenes_producto"
    __table_args__ = (
        CheckConstraint("orden >= 0", name="ck_imagenes_orden_no_negativo"),
        Index("ix_imagenes_producto_id", "producto_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    producto_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("productos.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    es_principal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    producto: Mapped[Producto] = relationship(back_populates="imagenes")
