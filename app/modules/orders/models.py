"""Modelos ORM de pedidos para los canales web, móvil y POS."""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class CanalPedido(StrEnum):
    WEB = "WEB"
    MOBILE = "MOBILE"
    POS = "POS"


class EstadoPedido(StrEnum):
    CREADO = "CREADO"
    PAGADO = "PAGADO"
    COMPLETADO = "COMPLETADO"
    CANCELADO = "CANCELADO"
    REEMBOLSADO = "REEMBOLSADO"


class Pedido(Base):
    __tablename__ = "pedidos"
    __table_args__ = (
        CheckConstraint("canal IN ('WEB','MOBILE','POS')", name="ck_pedidos_canal_valido"),
        CheckConstraint(
            "estado IN ('CREADO','PAGADO','COMPLETADO','CANCELADO','REEMBOLSADO')",
            name="ck_pedidos_estado_valido",
        ),
        CheckConstraint("subtotal >= 0", name="ck_pedidos_subtotal_no_negativo"),
        CheckConstraint("descuento >= 0", name="ck_pedidos_descuento_no_negativo"),
        CheckConstraint("total >= 0", name="ck_pedidos_total_no_negativo"),
        CheckConstraint("total = subtotal - descuento", name="ck_pedidos_total_consistente"),
        Index("ix_pedidos_cliente_id", "cliente_id"),
        Index("ix_pedidos_sucursal_creado", "sucursal_id", "creado_en"),
        Index("ix_pedidos_canal_estado", "canal", "estado"),
        Index("uq_pedidos_reserva_id", "reserva_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    cliente_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("usuarios.id", ondelete="RESTRICT")
    )
    sucursal_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("sucursales.id", ondelete="RESTRICT"), nullable=False
    )
    reserva_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("reservas.id", ondelete="RESTRICT")
    )
    canal: Mapped[str] = mapped_column(String(10), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    descuento: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    cliente: Mapped["Usuario | None"] = relationship(lazy="joined")  # type: ignore[name-defined] # noqa: F821
    sucursal: Mapped["Sucursal"] = relationship(lazy="joined")  # type: ignore[name-defined] # noqa: F821
    reserva: Mapped["Reserva | None"] = relationship(lazy="joined")  # type: ignore[name-defined] # noqa: F821
    detalles: Mapped[list["DetallePedido"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan", lazy="selectin"
    )
    pago: Mapped["Pago | None"] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="pedido", uselist=False, lazy="selectin"
    )
    devoluciones: Mapped[list["Devolucion"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="pedido", lazy="selectin"
    )

    @property
    def numero(self) -> str:
        return f"PED-{str(self.id).split('-')[0].upper()}"


class DetallePedido(Base):
    __tablename__ = "detalles_pedido"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_detalles_pedido_cantidad_positiva"),
        CheckConstraint("precio_unitario > 0", name="ck_detalles_pedido_precio_positivo"),
        CheckConstraint("subtotal > 0", name="ck_detalles_pedido_subtotal_positivo"),
        CheckConstraint(
            "subtotal = precio_unitario * cantidad", name="ck_detalles_pedido_subtotal_consistente"
        ),
        Index("ix_detalles_pedido_pedido_id", "pedido_id"),
        Index("ix_detalles_pedido_variante_id", "variante_id"),
        Index("uq_detalles_pedido_variante", "pedido_id", "variante_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    pedido_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("pedidos.id", ondelete="CASCADE"), nullable=False
    )
    variante_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("variantes_producto.id", ondelete="RESTRICT"), nullable=False
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    pedido: Mapped[Pedido] = relationship(back_populates="detalles")
    variante: Mapped["VarianteProducto"] = relationship(lazy="joined")  # type: ignore[name-defined] # noqa: F821
    devoluciones: Mapped[list["DetalleDevolucion"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="detalle_pedido", lazy="selectin"
    )

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
