"""Modelos ORM de pagos y reembolsos."""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class EstadoPago(StrEnum):
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    REEMBOLSADO = "REEMBOLSADO"


class MetodoPago(StrEnum):
    PASARELA_PRUEBA = "PASARELA_PRUEBA"
    STRIPE = "STRIPE"
    CAJA = "CAJA"


class Pago(Base):
    __tablename__ = "pagos"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('PENDIENTE','APROBADO','RECHAZADO','REEMBOLSADO')",
            name="ck_pagos_estado_valido",
        ),
        CheckConstraint(
            "metodo IN ('PASARELA_PRUEBA','STRIPE','CAJA')",
            name="ck_pagos_metodo_valido",
        ),
        CheckConstraint("monto > 0", name="ck_pagos_monto_positivo"),
        Index("uq_pagos_pedido_id", "pedido_id", unique=True),
        Index("uq_pagos_referencia_externa", "referencia_externa", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    pedido_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("pedidos.id", ondelete="RESTRICT"), nullable=False
    )
    metodo: Mapped[str] = mapped_column(String(30), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    referencia_externa: Mapped[str | None] = mapped_column(String(255))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    pagado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pedido: Mapped["Pedido"] = relationship(back_populates="pago")  # type: ignore[name-defined] # noqa: F821
    reembolsos: Mapped[list["Reembolso"]] = relationship(
        back_populates="pago", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def ambiente(self) -> str:
        if self.metodo == MetodoPago.PASARELA_PRUEBA.value:
            return "PRUEBA"
        if self.metodo == MetodoPago.STRIPE.value:
            return "STRIPE"
        return "LOCAL"

    @property
    def monto_reembolsado(self) -> Decimal:
        return sum((item.monto for item in self.reembolsos), start=Decimal("0.00"))


class Reembolso(Base):
    __tablename__ = "reembolsos"
    __table_args__ = (
        CheckConstraint("monto > 0", name="ck_reembolsos_monto_positivo"),
        Index("ix_reembolsos_pago_id", "pago_id"),
        Index("uq_reembolsos_devolucion_id", "devolucion_id", unique=True),
        Index("uq_reembolsos_referencia_externa", "referencia_externa", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    pago_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("pagos.id", ondelete="RESTRICT"), nullable=False
    )
    devolucion_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("devoluciones.id", ondelete="RESTRICT")
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    motivo: Mapped[str] = mapped_column(String(500), nullable=False)
    referencia_externa: Mapped[str | None] = mapped_column(String(255))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    pago: Mapped[Pago] = relationship(back_populates="reembolsos")
    devolucion: Mapped["Devolucion | None"] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="reembolso"
    )

    @property
    def estado(self) -> str:
        return "COMPLETADO"
