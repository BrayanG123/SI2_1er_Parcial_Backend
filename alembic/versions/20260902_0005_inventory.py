"""create inventory and movements

Revision ID: 20260902_0005
Revises: 20260902_0004
Create Date: 2026-09-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260902_0005"
down_revision: str | None = "20260902_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventarios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sucursal_id", sa.Uuid(), nullable=False),
        sa.Column("variante_id", sa.Uuid(), nullable=False),
        sa.Column("stock_fisico", sa.Integer(), nullable=False),
        sa.Column("stock_reservado", sa.Integer(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "stock_fisico >= 0", name="ck_inventarios_stock_fisico_no_negativo"
        ),
        sa.CheckConstraint(
            "stock_reservado >= 0", name="ck_inventarios_stock_reservado_no_negativo"
        ),
        sa.CheckConstraint(
            "stock_reservado <= stock_fisico",
            name="ck_inventarios_reservado_no_supera_fisico",
        ),
        sa.ForeignKeyConstraint(["sucursal_id"], ["sucursales.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["variante_id"], ["variantes_producto.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sucursal_id", "variante_id", name="uq_inventarios_sucursal_variante"
        ),
    )
    op.create_index("ix_inventarios_sucursal_id", "inventarios", ["sucursal_id"])
    op.create_index("ix_inventarios_variante_id", "inventarios", ["variante_id"])

    op.create_table(
        "movimientos_inventario",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("inventario_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("referencia_tipo", sa.String(length=50), nullable=True),
        sa.Column("referencia_id", sa.Uuid(), nullable=True),
        sa.Column("observacion", sa.String(length=500), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cantidad <> 0", name="ck_movimientos_cantidad_no_cero"),
        sa.CheckConstraint(
            "tipo IN ('RECEPCION','RESERVA','LIBERACION_RESERVA','VENTA','DEVOLUCION','AJUSTE')",
            name="ck_movimientos_tipo_valido",
        ),
        sa.ForeignKeyConstraint(
            ["inventario_id"], ["inventarios.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_movimientos_inventario_id", "movimientos_inventario", ["inventario_id"]
    )
    op.create_index(
        "ix_movimientos_creado_en", "movimientos_inventario", ["creado_en"]
    )
    op.create_index(
        "ix_movimientos_referencia",
        "movimientos_inventario",
        ["referencia_tipo", "referencia_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_movimientos_referencia", table_name="movimientos_inventario")
    op.drop_index("ix_movimientos_creado_en", table_name="movimientos_inventario")
    op.drop_index("ix_movimientos_inventario_id", table_name="movimientos_inventario")
    op.drop_table("movimientos_inventario")
    op.drop_index("ix_inventarios_variante_id", table_name="inventarios")
    op.drop_index("ix_inventarios_sucursal_id", table_name="inventarios")
    op.drop_table("inventarios")
