"""Modelos ORM de carritos y sus detalles."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Carrito(Base):
    __tablename__ = "carritos"
    __table_args__ = (
        Index("ix_carritos_cliente_id", "cliente_id"),
        Index(
            "uq_carritos_cliente_activo",
            "cliente_id",
            unique=True,
            postgresql_where=text("activo"),
            sqlite_where=text("activo = 1"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    cliente_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    cliente: Mapped["Usuario"] = relationship(lazy="joined")  # type: ignore[name-defined] # noqa: F821
    detalles: Mapped[list["DetalleCarrito"]] = relationship(
        back_populates="carrito", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def subtotal_estimado(self) -> Decimal:
        return sum((item.subtotal_estimado for item in self.detalles), start=Decimal("0.00"))


class DetalleCarrito(Base):
    __tablename__ = "detalles_carrito"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_detalles_carrito_cantidad_positiva"),
        Index("ix_detalles_carrito_carrito_id", "carrito_id"),
        Index("ix_detalles_carrito_variante_id", "variante_id"),
        Index("uq_detalles_carrito_variante", "carrito_id", "variante_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    carrito_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("carritos.id", ondelete="CASCADE"), nullable=False
    )
    variante_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("variantes_producto.id", ondelete="RESTRICT"), nullable=False
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)

    carrito: Mapped[Carrito] = relationship(back_populates="detalles")
    variante: Mapped["VarianteProducto"] = relationship(lazy="joined")  # type: ignore[name-defined] # noqa: F821

    @property
    def producto_id(self) -> UUID:
        return self.variante.producto_id

    @property
    def producto_nombre(self) -> str:
        return self.variante.producto.nombre

    @property
    def sku(self) -> str:
        return self.variante.sku

    @property
    def talla(self) -> str:
        return self.variante.talla.nombre

    @property
    def color(self) -> str:
        return self.variante.color.nombre

    @property
    def precio_unitario_estimado(self) -> Decimal:
        return self.variante.precio or self.variante.producto.precio_base

    @property
    def subtotal_estimado(self) -> Decimal:
        return self.precio_unitario_estimado * self.cantidad
