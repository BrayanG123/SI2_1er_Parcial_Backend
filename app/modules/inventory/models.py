"""Modelos ORM de existencias y movimientos de inventario."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class TipoMovimiento(StrEnum):
    RECEPCION = "RECEPCION"
    RESERVA = "RESERVA"
    LIBERACION_RESERVA = "LIBERACION_RESERVA"
    VENTA = "VENTA"
    DEVOLUCION = "DEVOLUCION"
    AJUSTE = "AJUSTE"


class Inventario(Base):
    __tablename__ = "inventarios"
    __table_args__ = (
        UniqueConstraint("sucursal_id", "variante_id", name="uq_inventarios_sucursal_variante"),
        CheckConstraint("stock_fisico >= 0", name="ck_inventarios_stock_fisico_no_negativo"),
        CheckConstraint("stock_reservado >= 0", name="ck_inventarios_stock_reservado_no_negativo"),
        CheckConstraint(
            "stock_reservado <= stock_fisico", name="ck_inventarios_reservado_no_supera_fisico"
        ),
        Index("ix_inventarios_sucursal_id", "sucursal_id"),
        Index("ix_inventarios_variante_id", "variante_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    sucursal_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("sucursales.id", ondelete="RESTRICT"), nullable=False
    )
    variante_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("variantes_producto.id", ondelete="RESTRICT"), nullable=False
    )
    stock_fisico: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock_reservado: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    sucursal: Mapped["Sucursal"] = relationship(lazy="joined")  # type: ignore[name-defined] # noqa: F821
    variante: Mapped["VarianteProducto"] = relationship(lazy="joined")  # type: ignore[name-defined] # noqa: F821
    movimientos: Mapped[list["MovimientoInventario"]] = relationship(
        back_populates="inventario", cascade="all, delete-orphan", lazy="select"
    )

    @hybrid_property
    def stock_disponible(self) -> int:
        return self.stock_fisico - self.stock_reservado

    @stock_disponible.expression
    def stock_disponible(cls):  # type: ignore[no-untyped-def]
        return cls.stock_fisico - cls.stock_reservado

    @property
    def producto(self):  # type: ignore[no-untyped-def]
        return self.variante.producto


class MovimientoInventario(Base):
    __tablename__ = "movimientos_inventario"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('RECEPCION','RESERVA','LIBERACION_RESERVA','VENTA','DEVOLUCION','AJUSTE')",
            name="ck_movimientos_tipo_valido",
        ),
        CheckConstraint("cantidad <> 0", name="ck_movimientos_cantidad_no_cero"),
        Index("ix_movimientos_inventario_id", "inventario_id"),
        Index("ix_movimientos_creado_en", "creado_en"),
        Index("ix_movimientos_referencia", "referencia_tipo", "referencia_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    inventario_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("inventarios.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    referencia_tipo: Mapped[str | None] = mapped_column(String(50))
    referencia_id: Mapped[UUID | None] = mapped_column(Uuid)
    observacion: Mapped[str | None] = mapped_column(String(500))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    inventario: Mapped[Inventario] = relationship(back_populates="movimientos")
