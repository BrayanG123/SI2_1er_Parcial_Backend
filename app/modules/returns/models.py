"""Modelos ORM de devoluciones y sus detalles."""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class EstadoDevolucion(StrEnum):
    SOLICITADA = "SOLICITADA"
    APROBADA = "APROBADA"
    COMPLETADA = "COMPLETADA"
    CANCELADA = "CANCELADA"


class Devolucion(Base):
    __tablename__ = "devoluciones"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('SOLICITADA','APROBADA','COMPLETADA','CANCELADA')",
            name="ck_devoluciones_estado_valido",
        ),
        Index("ix_devoluciones_pedido_id", "pedido_id"),
        Index("ix_devoluciones_cliente_id", "cliente_id"),
        Index("ix_devoluciones_estado_creada", "estado", "creada_en"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    pedido_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("pedidos.id", ondelete="RESTRICT"), nullable=False
    )
    cliente_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("usuarios.id", ondelete="RESTRICT")
    )
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    motivo_general: Mapped[str | None] = mapped_column(String(500))
    reingresa_stock: Mapped[bool | None] = mapped_column(Boolean)
    genera_reembolso: Mapped[bool | None] = mapped_column(Boolean)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pedido: Mapped["Pedido"] = relationship(back_populates="devoluciones")  # type: ignore[name-defined] # noqa: F821
    cliente: Mapped["Usuario | None"] = relationship(lazy="joined")  # type: ignore[name-defined] # noqa: F821
    detalles: Mapped[list["DetalleDevolucion"]] = relationship(
        back_populates="devolucion", cascade="all, delete-orphan", lazy="selectin"
    )
    reembolso: Mapped["Reembolso | None"] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="devolucion", uselist=False, lazy="joined"
    )

    @property
    def monto_estimado(self) -> Decimal:
        return sum(
            (
                item.detalle_pedido.precio_unitario * item.cantidad
                for item in self.detalles
            ),
            start=Decimal("0.00"),
        )


class DetalleDevolucion(Base):
    __tablename__ = "detalles_devolucion"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_detalles_devolucion_cantidad_positiva"),
        Index("ix_detalles_devolucion_devolucion_id", "devolucion_id"),
        Index("ix_detalles_devolucion_detalle_pedido_id", "detalle_pedido_id"),
        Index(
            "uq_detalles_devolucion_linea",
            "devolucion_id",
            "detalle_pedido_id",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    devolucion_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("devoluciones.id", ondelete="CASCADE"), nullable=False
    )
    detalle_pedido_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("detalles_pedido.id", ondelete="RESTRICT"), nullable=False
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(500))

    devolucion: Mapped[Devolucion] = relationship(back_populates="detalles")
    detalle_pedido: Mapped["DetallePedido"] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="devoluciones", lazy="joined"
    )

    @property
    def variante_id(self) -> UUID:
        return self.detalle_pedido.variante_id

    @property
    def producto_nombre(self) -> str:
        return self.detalle_pedido.producto_nombre

    @property
    def sku(self) -> str:
        return self.detalle_pedido.sku

    @property
    def talla(self) -> str:
        return self.detalle_pedido.talla

    @property
    def color(self) -> str:
        return self.detalle_pedido.color

    @property
    def precio_unitario(self) -> Decimal:
        return self.detalle_pedido.precio_unitario

    @property
    def subtotal(self) -> Decimal:
        return self.precio_unitario * self.cantidad
