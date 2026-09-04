"""Calcula reportes reproducibles sin depender de inteligencia artificial."""

from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.modules.branches.repository import BranchRepository
from app.modules.branches.schemas import SucursalRead
from app.modules.orders.models import CanalPedido
from app.modules.reports.repository import ReportRepository
from app.modules.reports.schemas import (
    ConteoPorEstado,
    DashboardReport,
    DevolucionesResumen,
    InventarioCritico,
    InventarioResumen,
    ProductoVendido,
    ReportFiltersRead,
    ReportOptions,
    ReporteDevoluciones,
    ReporteInventario,
    ReporteReservas,
    ReporteVentas,
    ReservasResumen,
    VentasPorCanal,
    VentasPorDia,
    VentasResumen,
)
from app.modules.reservations.models import EstadoReserva
from app.modules.returns.models import EstadoDevolucion
from app.modules.users.models import Usuario


MONEY = Decimal("0.01")
LOW_STOCK_THRESHOLD = 5


class ReportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.reports = ReportRepository(db)
        self.branches = BranchRepository(db)

    def options(self, *, user: Usuario) -> ReportOptions:
        branch_id = self._scoped_branch(user, None)
        if branch_id is not None:
            branch = self.branches.get_by_id(branch_id)
            if branch is None:
                raise NotFoundError("Sucursal asignada no encontrada.")
            rows = [branch]
        else:
            rows, _ = self.branches.list(
                offset=0, limit=1000, query=None, city_id=None, active=True
            )
        return ReportOptions(
            sucursales=[SucursalRead.model_validate(item) for item in rows]
        )

    def dashboard(
        self,
        *,
        user: Usuario,
        branch_id: UUID | None,
        date_from: date | None,
        date_to: date | None,
    ) -> DashboardReport:
        self._validate_dates(date_from, date_to)
        scoped_branch = self._scoped_branch(user, branch_id)
        return DashboardReport(
            generado_en=datetime.now(UTC),
            filtros=ReportFiltersRead(
                fecha_desde=date_from,
                fecha_hasta=date_to,
                sucursal_id=scoped_branch,
            ),
            ventas=self.sales(
                user=user,
                branch_id=scoped_branch,
                date_from=date_from,
                date_to=date_to,
                scope_resolved=True,
            ),
            inventario=self.inventory(
                user=user, branch_id=scoped_branch, scope_resolved=True
            ),
            reservas=self.reservations(
                user=user,
                branch_id=scoped_branch,
                date_from=date_from,
                date_to=date_to,
                scope_resolved=True,
            ),
            devoluciones=self.returns(
                user=user,
                branch_id=scoped_branch,
                date_from=date_from,
                date_to=date_to,
                scope_resolved=True,
            ),
        )

    def sales(
        self,
        *,
        user: Usuario,
        branch_id: UUID | None,
        date_from: date | None,
        date_to: date | None,
        scope_resolved: bool = False,
    ) -> ReporteVentas:
        self._validate_dates(date_from, date_to)
        scoped = branch_id if scope_resolved else self._scoped_branch(user, branch_id)
        rows = self.reports.sales_rows(
            branch_id=scoped, date_from=date_from, date_to=date_to
        )
        product_rows = self.reports.sales_by_product(
            branch_id=scoped, date_from=date_from, date_to=date_to
        )
        gross = sum((Decimal(row.total) for row in rows), start=Decimal("0.00"))
        refunds = self.reports.refunded_sales_total(
            branch_id=scoped, date_from=date_from, date_to=date_to
        )
        units = self.reports.sales_units(
            branch_id=scoped, date_from=date_from, date_to=date_to
        )

        channels: dict[str, tuple[int, Decimal]] = {
            channel.value: (0, Decimal("0.00")) for channel in CanalPedido
        }
        days: dict[date, tuple[int, Decimal]] = defaultdict(
            lambda: (0, Decimal("0.00"))
        )
        for row in rows:
            count, amount = channels[row.canal]
            channels[row.canal] = (count + 1, amount + Decimal(row.total))
            created_date = row.creado_en.date()
            count, amount = days[created_date]
            days[created_date] = (count + 1, amount + Decimal(row.total))

        order_count = len(rows)
        average = gross / order_count if order_count else Decimal("0.00")
        return ReporteVentas(
            resumen=VentasResumen(
                pedidos=order_count,
                unidades=units,
                venta_bruta=self._money(gross),
                reembolsos=self._money(refunds),
                venta_neta=self._money(gross - refunds),
                ticket_promedio=self._money(average),
            ),
            por_canal=[
                VentasPorCanal(canal=name, pedidos=value[0], monto=self._money(value[1]))
                for name, value in channels.items()
            ],
            por_dia=[
                VentasPorDia(fecha=day, pedidos=value[0], monto=self._money(value[1]))
                for day, value in sorted(days.items())
            ],
            productos_destacados=[
                ProductoVendido(
                    producto_id=row.id,
                    producto_nombre=row.nombre,
                    unidades=int(row.unidades),
                    monto=self._money(Decimal(row.monto)),
                )
                for row in product_rows
            ],
        )

    def inventory(
        self,
        *,
        user: Usuario,
        branch_id: UUID | None,
        scope_resolved: bool = False,
    ) -> ReporteInventario:
        scoped = branch_id if scope_resolved else self._scoped_branch(user, branch_id)
        rows = self.reports.inventory_rows(branch_id=scoped)
        critical = [row for row in rows if int(row.stock_disponible) <= LOW_STOCK_THRESHOLD]
        return ReporteInventario(
            resumen=InventarioResumen(
                registros=len(rows),
                stock_fisico=sum(int(row.stock_fisico) for row in rows),
                stock_reservado=sum(int(row.stock_reservado) for row in rows),
                stock_disponible=sum(int(row.stock_disponible) for row in rows),
                agotados=sum(int(row.stock_disponible) == 0 for row in rows),
                stock_bajo=sum(
                    0 < int(row.stock_disponible) <= LOW_STOCK_THRESHOLD for row in rows
                ),
                umbral_stock_bajo=LOW_STOCK_THRESHOLD,
            ),
            existencias_criticas=[
                InventarioCritico(
                    inventario_id=row.id,
                    sucursal_id=row.sucursal_id,
                    sucursal_nombre=row.sucursal_nombre,
                    producto_id=row.producto_id,
                    producto_nombre=row.producto_nombre,
                    variante_id=row.variante_id,
                    sku=row.sku,
                    stock_fisico=row.stock_fisico,
                    stock_reservado=row.stock_reservado,
                    stock_disponible=row.stock_disponible,
                )
                for row in critical[:20]
            ],
        )

    def reservations(
        self,
        *,
        user: Usuario,
        branch_id: UUID | None,
        date_from: date | None,
        date_to: date | None,
        scope_resolved: bool = False,
    ) -> ReporteReservas:
        self._validate_dates(date_from, date_to)
        scoped = branch_id if scope_resolved else self._scoped_branch(user, branch_id)
        rows = self.reports.reservation_rows(
            branch_id=scoped, date_from=date_from, date_to=date_to
        )
        state_counts = {state.value: 0 for state in EstadoReserva}
        for row in rows:
            state_counts[row.estado] += 1
        converted = self.reports.converted_reservations(
            branch_id=scoped, date_from=date_from, date_to=date_to
        )
        total = len(rows)
        conversion = Decimal(converted * 100) / total if total else Decimal("0.00")
        return ReporteReservas(
            resumen=ReservasResumen(
                reservas=total,
                unidades=self.reports.reservation_units(
                    branch_id=scoped, date_from=date_from, date_to=date_to
                ),
                convertidas_en_pedido=converted,
                tasa_conversion=self._money(conversion),
            ),
            por_estado=[
                ConteoPorEstado(estado=state, cantidad=count)
                for state, count in state_counts.items()
            ],
        )

    def returns(
        self,
        *,
        user: Usuario,
        branch_id: UUID | None,
        date_from: date | None,
        date_to: date | None,
        scope_resolved: bool = False,
    ) -> ReporteDevoluciones:
        self._validate_dates(date_from, date_to)
        scoped = branch_id if scope_resolved else self._scoped_branch(user, branch_id)
        rows = self.reports.return_rows(
            branch_id=scoped, date_from=date_from, date_to=date_to
        )
        state_counts = {state.value: 0 for state in EstadoDevolucion}
        for row in rows:
            state_counts[row.estado] += 1
        units, requested = self.reports.return_units_and_amount(
            branch_id=scoped, date_from=date_from, date_to=date_to
        )
        refunded = self.reports.return_refunded_total(
            branch_id=scoped, date_from=date_from, date_to=date_to
        )
        return ReporteDevoluciones(
            resumen=DevolucionesResumen(
                devoluciones=len(rows),
                unidades=units,
                monto_solicitado=self._money(requested),
                monto_reembolsado=self._money(refunded),
            ),
            por_estado=[
                ConteoPorEstado(estado=state, cantidad=count)
                for state, count in state_counts.items()
            ],
        )

    def _scoped_branch(self, user: Usuario, requested: UUID | None) -> UUID | None:
        if any(role.nombre == "administrador" for role in user.roles):
            if requested is not None and self.branches.get_by_id(requested) is None:
                raise NotFoundError("Sucursal no encontrada.")
            return requested
        if user.sucursal_id is None:
            raise ForbiddenError("Tu usuario no tiene una sucursal asignada.")
        if requested is not None and requested != user.sucursal_id:
            raise ForbiddenError("Solo puedes consultar reportes de tu sucursal.")
        return user.sucursal_id

    @staticmethod
    def _validate_dates(date_from: date | None, date_to: date | None) -> None:
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ConflictError("La fecha inicial no puede ser posterior a la fecha final.")

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(MONEY, rounding=ROUND_HALF_UP)
