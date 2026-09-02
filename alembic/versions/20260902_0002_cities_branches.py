"""create cities and branches

Revision ID: 20260902_0002
Revises: 20260901_0001
Create Date: 2026-09-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260902_0002"
down_revision: str | None = "20260901_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ciudades",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("departamento", sa.String(length=120), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ciudades_nombre", "ciudades", ["nombre"], unique=True)

    op.create_table(
        "sucursales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ciudad_id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("direccion", sa.String(length=500), nullable=False),
        sa.Column("telefono", sa.String(length=30), nullable=True),
        sa.Column("horario_informativo", sa.String(length=255), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["ciudad_id"], ["ciudades.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ciudad_id", "nombre", name="uq_sucursales_ciudad_nombre"),
    )
    op.create_index("ix_sucursales_ciudad_id", "sucursales", ["ciudad_id"])
    op.create_foreign_key(
        "fk_usuarios_sucursal_id_sucursales",
        "usuarios",
        "sucursales",
        ["sucursal_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_usuarios_sucursal_id_sucursales", "usuarios", type_="foreignkey")
    op.drop_index("ix_sucursales_ciudad_id", table_name="sucursales")
    op.drop_table("sucursales")
    op.drop_index("ix_ciudades_nombre", table_name="ciudades")
    op.drop_table("ciudades")
