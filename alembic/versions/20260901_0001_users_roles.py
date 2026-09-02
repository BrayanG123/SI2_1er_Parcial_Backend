"""create users roles and customer profiles

Revision ID: 20260901_0001
Revises:
Create Date: 2026-09-01
"""

from collections.abc import Sequence
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision: str = "20260901_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INITIAL_ROLES = (
    (UUID("00000000-0000-0000-0000-000000000001"), "cliente", "Cliente de la tienda"),
    (UUID("00000000-0000-0000-0000-000000000002"), "administrador", "Administrador"),
    (UUID("00000000-0000-0000-0000-000000000003"), "encargado", "Encargado de sucursal"),
    (UUID("00000000-0000-0000-0000-000000000004"), "cajero", "Cajero de sucursal"),
)


def upgrade() -> None:
    roles = op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=50), nullable=False),
        sa.Column("descripcion", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_roles_nombre", "roles", ["nombre"], unique=True)

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("nombres", sa.String(length=120), nullable=False),
        sa.Column("apellidos", sa.String(length=120), nullable=False),
        sa.Column("telefono", sa.String(length=30), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("sucursal_id", sa.Uuid(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)

    op.create_table(
        "perfiles_cliente",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("direccion", sa.String(length=500), nullable=True),
        sa.Column("preferencias_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usuario_id"),
    )

    op.create_table(
        "usuario_roles",
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("rol_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["rol_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("usuario_id", "rol_id"),
    )

    op.bulk_insert(
        roles,
        [{"id": role_id, "nombre": name, "descripcion": description} for role_id, name, description in INITIAL_ROLES],
    )


def downgrade() -> None:
    op.drop_table("usuario_roles")
    op.drop_table("perfiles_cliente")
    op.drop_index("ix_usuarios_email", table_name="usuarios")
    op.drop_table("usuarios")
    op.drop_index("ix_roles_nombre", table_name="roles")
    op.drop_table("roles")
