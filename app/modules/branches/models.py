"""Modelos ORM de ciudades y sucursales."""

from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Ciudad(Base):
    __tablename__ = "ciudades"
    __table_args__ = (Index("ix_ciudades_nombre", "nombre", unique=True),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    departamento: Mapped[str | None] = mapped_column(String(120))
    sucursales: Mapped[list["Sucursal"]] = relationship(back_populates="ciudad", lazy="selectin")


class Sucursal(Base):
    __tablename__ = "sucursales"
    __table_args__ = (
        UniqueConstraint("ciudad_id", "nombre", name="uq_sucursales_ciudad_nombre"),
        Index("ix_sucursales_ciudad_id", "ciudad_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    ciudad_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("ciudades.id", ondelete="RESTRICT"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    direccion: Mapped[str] = mapped_column(String(500), nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(30))
    horario_informativo: Mapped[str] = mapped_column(String(255), nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    ciudad: Mapped[Ciudad] = relationship(back_populates="sucursales", lazy="joined")
    empleados: Mapped[list["Usuario"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="sucursal", passive_deletes=True
    )
