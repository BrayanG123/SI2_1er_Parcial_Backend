"""create carts and unified orders

Revision ID: 20260902_0007
Revises: 20260902_0006
Create Date: 2026-09-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260902_0007"
down_revision: str | None = "20260902_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "carritos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cliente_id", sa.Uuid(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cliente_id"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_carritos_cliente_id", "carritos", ["cliente_id"])
    op.create_index(
        "uq_carritos_cliente_activo",
        "carritos",
        ["cliente_id"],
        unique=True,
        postgresql_where=sa.text("activo"),
    )

    op.create_table(
        "pedidos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cliente_id", sa.Uuid(), nullable=True),
        sa.Column("sucursal_id", sa.Uuid(), nullable=False),
        sa.Column("reserva_id", sa.Uuid(), nullable=True),
        sa.Column("canal", sa.String(length=10), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("descuento", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("canal IN ('WEB','MOBILE','POS')", name="ck_pedidos_canal_valido"),
        sa.CheckConstraint(
            "estado IN ('CREADO','PAGADO','COMPLETADO','CANCELADO','REEMBOLSADO')",
            name="ck_pedidos_estado_valido",
        ),
        sa.CheckConstraint("descuento >= 0", name="ck_pedidos_descuento_no_negativo"),
        sa.CheckConstraint("subtotal >= 0", name="ck_pedidos_subtotal_no_negativo"),
        sa.CheckConstraint("total >= 0", name="ck_pedidos_total_no_negativo"),
        sa.CheckConstraint("total = subtotal - descuento", name="ck_pedidos_total_consistente"),
        sa.ForeignKeyConstraint(["cliente_id"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reserva_id"], ["reservas.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sucursal_id"], ["sucursales.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pedidos_cliente_id", "pedidos", ["cliente_id"])
    op.create_index("ix_pedidos_sucursal_creado", "pedidos", ["sucursal_id", "creado_en"])
    op.create_index("ix_pedidos_canal_estado", "pedidos", ["canal", "estado"])
    op.create_index("uq_pedidos_reserva_id", "pedidos", ["reserva_id"], unique=True)

    op.create_table(
        "detalles_carrito",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("carrito_id", sa.Uuid(), nullable=False),
        sa.Column("variante_id", sa.Uuid(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.CheckConstraint("cantidad > 0", name="ck_detalles_carrito_cantidad_positiva"),
        sa.ForeignKeyConstraint(["carrito_id"], ["carritos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variante_id"], ["variantes_producto.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_detalles_carrito_carrito_id", "detalles_carrito", ["carrito_id"])
    op.create_index("ix_detalles_carrito_variante_id", "detalles_carrito", ["variante_id"])
    op.create_index(
        "uq_detalles_carrito_variante",
        "detalles_carrito",
        ["carrito_id", "variante_id"],
        unique=True,
    )

    op.create_table(
        "detalles_pedido",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pedido_id", sa.Uuid(), nullable=False),
        sa.Column("variante_id", sa.Uuid(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint("cantidad > 0", name="ck_detalles_pedido_cantidad_positiva"),
        sa.CheckConstraint("precio_unitario > 0", name="ck_detalles_pedido_precio_positivo"),
        sa.CheckConstraint("subtotal > 0", name="ck_detalles_pedido_subtotal_positivo"),
        sa.CheckConstraint(
            "subtotal = precio_unitario * cantidad",
            name="ck_detalles_pedido_subtotal_consistente",
        ),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedidos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variante_id"], ["variantes_producto.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_detalles_pedido_pedido_id", "detalles_pedido", ["pedido_id"])
    op.create_index("ix_detalles_pedido_variante_id", "detalles_pedido", ["variante_id"])
    op.create_index(
        "uq_detalles_pedido_variante",
        "detalles_pedido",
        ["pedido_id", "variante_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_detalles_pedido_variante", table_name="detalles_pedido")
    op.drop_index("ix_detalles_pedido_variante_id", table_name="detalles_pedido")
    op.drop_index("ix_detalles_pedido_pedido_id", table_name="detalles_pedido")
    op.drop_table("detalles_pedido")
    op.drop_index("uq_detalles_carrito_variante", table_name="detalles_carrito")
    op.drop_index("ix_detalles_carrito_variante_id", table_name="detalles_carrito")
    op.drop_index("ix_detalles_carrito_carrito_id", table_name="detalles_carrito")
    op.drop_table("detalles_carrito")
    op.drop_index("uq_pedidos_reserva_id", table_name="pedidos")
    op.drop_index("ix_pedidos_canal_estado", table_name="pedidos")
    op.drop_index("ix_pedidos_sucursal_creado", table_name="pedidos")
    op.drop_index("ix_pedidos_cliente_id", table_name="pedidos")
    op.drop_table("pedidos")
    op.drop_index("uq_carritos_cliente_activo", table_name="carritos")
    op.drop_index("ix_carritos_cliente_id", table_name="carritos")
    op.drop_table("carritos")
