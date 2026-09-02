"""create categories and suppliers

Revision ID: 20260902_0003
Revises: 20260902_0002
Create Date: 2026-09-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260902_0003"
down_revision: str | None = "20260902_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categorias",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("descripcion", sa.String(length=500), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_categorias_nombre", "categorias", ["nombre"], unique=True)

    op.create_table(
        "proveedores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=160), nullable=False),
        sa.Column("nit", sa.String(length=50), nullable=True),
        sa.Column("telefono", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("direccion", sa.String(length=500), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_proveedores_nombre", "proveedores", ["nombre"], unique=True)
    op.create_index("ix_proveedores_nit", "proveedores", ["nit"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_proveedores_nit", table_name="proveedores")
    op.drop_index("ix_proveedores_nombre", table_name="proveedores")
    op.drop_table("proveedores")
    op.drop_index("ix_categorias_nombre", table_name="categorias")
    op.drop_table("categorias")
