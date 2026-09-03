"""create payments refunds and returns

Revision ID: 20260902_0008
Revises: 20260902_0007
Create Date: 2026-09-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260902_0008"
down_revision: str | None = "20260902_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pagos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pedido_id", sa.Uuid(), nullable=False),
        sa.Column("metodo", sa.String(length=30), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("monto", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("referencia_externa", sa.String(length=255), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pagado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estado IN ('PENDIENTE','APROBADO','RECHAZADO','REEMBOLSADO')",
            name="ck_pagos_estado_valido",
        ),
        sa.CheckConstraint(
            "metodo IN ('PASARELA_PRUEBA','CAJA')",
            name="ck_pagos_metodo_valido",
        ),
        sa.CheckConstraint("monto > 0", name="ck_pagos_monto_positivo"),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedidos.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_pagos_pedido_id", "pagos", ["pedido_id"], unique=True)
    op.create_index(
        "uq_pagos_referencia_externa",
        "pagos",
        ["referencia_externa"],
        unique=True,
    )

    op.create_table(
        "devoluciones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pedido_id", sa.Uuid(), nullable=False),
        sa.Column("cliente_id", sa.Uuid(), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("motivo_general", sa.String(length=500), nullable=True),
        sa.Column("reingresa_stock", sa.Boolean(), nullable=True),
        sa.Column("genera_reembolso", sa.Boolean(), nullable=True),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completada_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estado IN ('SOLICITADA','APROBADA','COMPLETADA','CANCELADA')",
            name="ck_devoluciones_estado_valido",
        ),
        sa.ForeignKeyConstraint(["cliente_id"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedidos.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_devoluciones_pedido_id", "devoluciones", ["pedido_id"])
    op.create_index("ix_devoluciones_cliente_id", "devoluciones", ["cliente_id"])
    op.create_index(
        "ix_devoluciones_estado_creada",
        "devoluciones",
        ["estado", "creada_en"],
    )

    op.create_table(
        "detalles_devolucion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("devolucion_id", sa.Uuid(), nullable=False),
        sa.Column("detalle_pedido_id", sa.Uuid(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("motivo", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "cantidad > 0", name="ck_detalles_devolucion_cantidad_positiva"
        ),
        sa.ForeignKeyConstraint(
            ["detalle_pedido_id"], ["detalles_pedido.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["devolucion_id"], ["devoluciones.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_detalles_devolucion_devolucion_id",
        "detalles_devolucion",
        ["devolucion_id"],
    )
    op.create_index(
        "ix_detalles_devolucion_detalle_pedido_id",
        "detalles_devolucion",
        ["detalle_pedido_id"],
    )
    op.create_index(
        "uq_detalles_devolucion_linea",
        "detalles_devolucion",
        ["devolucion_id", "detalle_pedido_id"],
        unique=True,
    )

    op.create_table(
        "reembolsos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pago_id", sa.Uuid(), nullable=False),
        sa.Column("devolucion_id", sa.Uuid(), nullable=True),
        sa.Column("monto", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("motivo", sa.String(length=500), nullable=False),
        sa.Column("referencia_externa", sa.String(length=255), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("monto > 0", name="ck_reembolsos_monto_positivo"),
        sa.ForeignKeyConstraint(
            ["devolucion_id"], ["devoluciones.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["pago_id"], ["pagos.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reembolsos_pago_id", "reembolsos", ["pago_id"])
    op.create_index(
        "uq_reembolsos_devolucion_id",
        "reembolsos",
        ["devolucion_id"],
        unique=True,
    )
    op.create_index(
        "uq_reembolsos_referencia_externa",
        "reembolsos",
        ["referencia_externa"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_reembolsos_referencia_externa", table_name="reembolsos")
    op.drop_index("uq_reembolsos_devolucion_id", table_name="reembolsos")
    op.drop_index("ix_reembolsos_pago_id", table_name="reembolsos")
    op.drop_table("reembolsos")
    op.drop_index("uq_detalles_devolucion_linea", table_name="detalles_devolucion")
    op.drop_index(
        "ix_detalles_devolucion_detalle_pedido_id",
        table_name="detalles_devolucion",
    )
    op.drop_index(
        "ix_detalles_devolucion_devolucion_id", table_name="detalles_devolucion"
    )
    op.drop_table("detalles_devolucion")
    op.drop_index("ix_devoluciones_estado_creada", table_name="devoluciones")
    op.drop_index("ix_devoluciones_cliente_id", table_name="devoluciones")
    op.drop_index("ix_devoluciones_pedido_id", table_name="devoluciones")
    op.drop_table("devoluciones")
    op.drop_index("uq_pagos_referencia_externa", table_name="pagos")
    op.drop_index("uq_pagos_pedido_id", table_name="pagos")
    op.drop_table("pagos")
