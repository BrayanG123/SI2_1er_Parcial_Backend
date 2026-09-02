"""Modelo ORM con los datos básicos del proveedor."""

from uuid import UUID, uuid4

from sqlalchemy import Boolean, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Proveedor(Base):
    __tablename__ = "proveedores"
    __table_args__ = (
        Index("ix_proveedores_nombre", "nombre", unique=True),
        Index("ix_proveedores_nit", "nit", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    nit: Mapped[str | None] = mapped_column(String(50))
    telefono: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(320))
    direccion: Mapped[str | None] = mapped_column(String(500))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
