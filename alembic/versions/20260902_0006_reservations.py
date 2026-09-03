"""create reservations and details

Revision ID: 20260902_0006
Revises: 20260902_0005
Create Date: 2026-09-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260902_0006"
down_revision: str | None = "20260902_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reservas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cliente_id", sa.Uuid(), nullable=False),
        sa.Column("sucursal_id", sa.Uuid(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("fecha_visita", sa.Date(), nullable=False),
        sa.Column("hora_aproximada", sa.Time(), nullable=True),
        sa.Column("vence_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelada_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estado IN ('PENDIENTE','CONFIRMADA','PREPARADA','COMPLETADA','CANCELADA','VENCIDA')",
            name="ck_reservas_estado_valido",
        ),
        sa.ForeignKeyConstraint(["cliente_id"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sucursal_id"], ["sucursales.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reservas_cliente_id", "reservas", ["cliente_id"])
    op.create_index("ix_reservas_sucursal_estado", "reservas", ["sucursal_id", "estado"])
    op.create_index("ix_reservas_vence_en", "reservas", ["vence_en"])
    op.create_index("ix_reservas_fecha_visita", "reservas", ["fecha_visita"])

    op.create_table(
        "detalles_reserva",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reserva_id", sa.Uuid(), nullable=False),
        sa.Column("inventario_id", sa.Uuid(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.CheckConstraint("cantidad > 0", name="ck_detalles_reserva_cantidad_positiva"),
        sa.ForeignKeyConstraint(["inventario_id"], ["inventarios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reserva_id"], ["reservas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reserva_id", "inventario_id", name="uq_detalles_reserva_inventario"
        ),
    )
    op.create_index(
        "ix_detalles_reserva_reserva_id", "detalles_reserva", ["reserva_id"]
    )
    op.create_index(
        "ix_detalles_reserva_inventario_id", "detalles_reserva", ["inventario_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_detalles_reserva_inventario_id", table_name="detalles_reserva")
    op.drop_index("ix_detalles_reserva_reserva_id", table_name="detalles_reserva")
    op.drop_table("detalles_reserva")
    op.drop_index("ix_reservas_fecha_visita", table_name="reservas")
    op.drop_index("ix_reservas_vence_en", table_name="reservas")
    op.drop_index("ix_reservas_sucursal_estado", table_name="reservas")
    op.drop_index("ix_reservas_cliente_id", table_name="reservas")
    op.drop_table("reservas")
