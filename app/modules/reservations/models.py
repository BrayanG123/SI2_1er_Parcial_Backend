"""Modelos ORM de reservas y sus detalles."""

from datetime import UTC, date, datetime, time
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Time, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class EstadoReserva(StrEnum):
    PENDIENTE = "PENDIENTE"
    CONFIRMADA = "CONFIRMADA"
    PREPARADA = "PREPARADA"
    COMPLETADA = "COMPLETADA"
    CANCELADA = "CANCELADA"
    VENCIDA = "VENCIDA"


class Reserva(Base):
    __tablename__ = "reservas"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('PENDIENTE','CONFIRMADA','PREPARADA','COMPLETADA','CANCELADA','VENCIDA')",
            name="ck_reservas_estado_valido",
        ),
        Index("ix_reservas_cliente_id", "cliente_id"),
        Index("ix_reservas_sucursal_estado", "sucursal_id", "estado"),
        Index("ix_reservas_vence_en", "vence_en"),
        Index("ix_reservas_fecha_visita", "fecha_visita"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    cliente_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    sucursal_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("sucursales.id", ondelete="RESTRICT"), nullable=False
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EstadoReserva.PENDIENTE.value
    )
    fecha_visita: Mapped[date] = mapped_column(Date, nullable=False)
    hora_aproximada: Mapped[time | None] = mapped_column(Time)
    vence_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    cancelada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    cliente: Mapped["Usuario"] = relationship(lazy="joined")  # type: ignore[name-defined] # noqa: F821
    sucursal: Mapped["Sucursal"] = relationship(lazy="joined")  # type: ignore[name-defined] # noqa: F821
    detalles: Mapped[list["DetalleReserva"]] = relationship(
        back_populates="reserva",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DetalleReserva.id",
    )


class DetalleReserva(Base):
    __tablename__ = "detalles_reserva"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_detalles_reserva_cantidad_positiva"),
        UniqueConstraint(
            "reserva_id", "inventario_id", name="uq_detalles_reserva_inventario"
        ),
        Index("ix_detalles_reserva_reserva_id", "reserva_id"),
        Index("ix_detalles_reserva_inventario_id", "inventario_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    reserva_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("reservas.id", ondelete="CASCADE"), nullable=False
    )
    inventario_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("inventarios.id", ondelete="RESTRICT"), nullable=False
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)

    reserva: Mapped[Reserva] = relationship(back_populates="detalles")
    inventario: Mapped["Inventario"] = relationship(lazy="joined")  # type: ignore[name-defined] # noqa: F821

    @property
    def variante_id(self) -> UUID:
        return self.inventario.variante_id

    @property
    def producto_id(self) -> UUID:
        return self.inventario.variante.producto_id

    @property
    def producto_nombre(self) -> str:
        return self.inventario.variante.producto.nombre

    @property
    def sku(self) -> str:
        return self.inventario.variante.sku

    @property
    def talla(self) -> str:
        return self.inventario.variante.talla.nombre

    @property
    def color(self) -> str:
        return self.inventario.variante.color.nombre
