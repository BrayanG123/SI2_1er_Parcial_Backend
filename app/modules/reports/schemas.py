"""Filtros y resultados reproducibles de reportes deterministas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.branches.schemas import SucursalRead


class ReportFiltersRead(BaseModel):
    fecha_desde: date | None = None
    fecha_hasta: date | None = None
    sucursal_id: UUID | None = None


class ReportOptions(BaseModel):
    sucursales: list[SucursalRead]


class VentasResumen(BaseModel):
    pedidos: int
    unidades: int
    venta_bruta: Decimal
    reembolsos: Decimal
    venta_neta: Decimal
    ticket_promedio: Decimal


class VentasPorCanal(BaseModel):
    canal: str
    pedidos: int
    monto: Decimal


class VentasPorDia(BaseModel):
    fecha: date
    pedidos: int
    monto: Decimal


class ProductoVendido(BaseModel):
    producto_id: UUID
    producto_nombre: str
    unidades: int
    monto: Decimal


class ReporteVentas(BaseModel):
    resumen: VentasResumen
    por_canal: list[VentasPorCanal]
    por_dia: list[VentasPorDia]
    productos_destacados: list[ProductoVendido]


class InventarioResumen(BaseModel):
    registros: int
    stock_fisico: int
    stock_reservado: int
    stock_disponible: int
    agotados: int
    stock_bajo: int
    umbral_stock_bajo: int


class InventarioCritico(BaseModel):
    inventario_id: UUID
    sucursal_id: UUID
    sucursal_nombre: str
    producto_id: UUID
    producto_nombre: str
    variante_id: UUID
    sku: str
    stock_fisico: int
    stock_reservado: int
    stock_disponible: int


class ReporteInventario(BaseModel):
    resumen: InventarioResumen
    existencias_criticas: list[InventarioCritico]


class ConteoPorEstado(BaseModel):
    estado: str
    cantidad: int


class ReservasResumen(BaseModel):
    reservas: int
    unidades: int
    convertidas_en_pedido: int
    tasa_conversion: Decimal = Field(decimal_places=2)


class ReporteReservas(BaseModel):
    resumen: ReservasResumen
    por_estado: list[ConteoPorEstado]


class DevolucionesResumen(BaseModel):
    devoluciones: int
    unidades: int
    monto_solicitado: Decimal
    monto_reembolsado: Decimal


class ReporteDevoluciones(BaseModel):
    resumen: DevolucionesResumen
    por_estado: list[ConteoPorEstado]


class DashboardReport(BaseModel):
    generado_en: datetime
    filtros: ReportFiltersRead
    ventas: ReporteVentas
    inventario: ReporteInventario
    reservas: ReporteReservas
    devoluciones: ReporteDevoluciones
