"""create clothing catalog

Revision ID: 20260902_0004
Revises: 20260902_0003
Create Date: 2026-09-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260902_0004"
down_revision: str | None = "20260902_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tallas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=50), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=True),
        sa.CheckConstraint("orden IS NULL OR orden >= 0", name="ck_tallas_orden_no_negativo"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tallas_nombre", "tallas", ["nombre"], unique=True)

    op.create_table(
        "colores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("codigo_hex", sa.String(length=7), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_colores_nombre", "colores", ["nombre"], unique=True)

    op.create_table(
        "temporadas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=True),
        sa.Column("fecha_fin", sa.Date(), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "fecha_inicio IS NULL OR fecha_fin IS NULL OR fecha_inicio <= fecha_fin",
            name="ck_temporadas_fechas",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_temporadas_nombre", "temporadas", ["nombre"], unique=True)

    op.create_table(
        "colecciones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("temporada_id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("descripcion", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["temporada_id"], ["temporadas.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("temporada_id", "nombre", name="uq_colecciones_temporada_nombre"),
    )
    op.create_index("ix_colecciones_temporada_id", "colecciones", ["temporada_id"])

    op.create_table(
        "productos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("categoria_id", sa.Uuid(), nullable=False),
        sa.Column("proveedor_id", sa.Uuid(), nullable=False),
        sa.Column("temporada_id", sa.Uuid(), nullable=True),
        sa.Column("coleccion_id", sa.Uuid(), nullable=True),
        sa.Column("nombre", sa.String(length=180), nullable=False),
        sa.Column("descripcion", sa.String(length=1000), nullable=True),
        sa.Column("marca", sa.String(length=120), nullable=True),
        sa.Column("precio_base", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.CheckConstraint("precio_base > 0", name="ck_productos_precio_positivo"),
        sa.ForeignKeyConstraint(["categoria_id"], ["categorias.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["proveedor_id"], ["proveedores.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["temporada_id"], ["temporadas.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["coleccion_id"], ["colecciones.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("nombre", "categoria_id", "proveedor_id", "temporada_id", "coleccion_id"):
        op.create_index(f"ix_productos_{column}", "productos", [column])

    op.create_table(
        "variantes_producto",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("producto_id", sa.Uuid(), nullable=False),
        sa.Column("talla_id", sa.Uuid(), nullable=False),
        sa.Column("color_id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(length=80), nullable=False),
        sa.Column("precio", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.CheckConstraint("precio IS NULL OR precio > 0", name="ck_variantes_precio_positivo"),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["talla_id"], ["tallas.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["color_id"], ["colores.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "producto_id", "talla_id", "color_id", name="uq_variantes_producto_talla_color"
        ),
    )
    op.create_index("ix_variantes_sku", "variantes_producto", ["sku"], unique=True)
    op.create_index("ix_variantes_producto_id", "variantes_producto", ["producto_id"])
    op.create_index("ix_variantes_talla_id", "variantes_producto", ["talla_id"])
    op.create_index("ix_variantes_color_id", "variantes_producto", ["color_id"])

    op.create_table(
        "imagenes_producto",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("producto_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("es_principal", sa.Boolean(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.CheckConstraint("orden >= 0", name="ck_imagenes_orden_no_negativo"),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_imagenes_producto_id", "imagenes_producto", ["producto_id"])


def downgrade() -> None:
    op.drop_index("ix_imagenes_producto_id", table_name="imagenes_producto")
    op.drop_table("imagenes_producto")
    for index in ("ix_variantes_color_id", "ix_variantes_talla_id", "ix_variantes_producto_id", "ix_variantes_sku"):
        op.drop_index(index, table_name="variantes_producto")
    op.drop_table("variantes_producto")
    for column in ("coleccion_id", "temporada_id", "proveedor_id", "categoria_id", "nombre"):
        op.drop_index(f"ix_productos_{column}", table_name="productos")
    op.drop_table("productos")
    op.drop_index("ix_colecciones_temporada_id", table_name="colecciones")
    op.drop_table("colecciones")
    op.drop_index("ix_temporadas_nombre", table_name="temporadas")
    op.drop_table("temporadas")
    op.drop_index("ix_colores_nombre", table_name="colores")
    op.drop_table("colores")
    op.drop_index("ix_tallas_nombre", table_name="tallas")
    op.drop_table("tallas")
