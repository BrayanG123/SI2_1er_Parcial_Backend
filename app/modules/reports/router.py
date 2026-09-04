"""Endpoints de reportes deterministas."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.reports.schemas import (
    DashboardReport,
    ReportOptions,
    ReporteDevoluciones,
    ReporteInventario,
    ReporteReservas,
    ReporteVentas,
)
from app.modules.reports.service import ReportService
from app.modules.users.models import Usuario


router = APIRouter(prefix="/reports", tags=["reports"])
ReportReader = Annotated[
    Usuario, Depends(require_roles("administrador", "encargado"))
]


@router.get("/options", response_model=ReportOptions)
def report_options(
    current_user: ReportReader, db: Annotated[Session, Depends(get_db)]
) -> ReportOptions:
    return ReportService(db).options(user=current_user)


@router.get("/dashboard", response_model=DashboardReport)
def dashboard(
    current_user: ReportReader,
    db: Annotated[Session, Depends(get_db)],
    branch_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> DashboardReport:
    return ReportService(db).dashboard(
        user=current_user,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/sales", response_model=ReporteVentas)
def sales_report(
    current_user: ReportReader,
    db: Annotated[Session, Depends(get_db)],
    branch_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> ReporteVentas:
    return ReportService(db).sales(
        user=current_user,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/inventory", response_model=ReporteInventario)
def inventory_report(
    current_user: ReportReader,
    db: Annotated[Session, Depends(get_db)],
    branch_id: UUID | None = None,
) -> ReporteInventario:
    return ReportService(db).inventory(user=current_user, branch_id=branch_id)


@router.get("/reservations", response_model=ReporteReservas)
def reservations_report(
    current_user: ReportReader,
    db: Annotated[Session, Depends(get_db)],
    branch_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> ReporteReservas:
    return ReportService(db).reservations(
        user=current_user,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/returns", response_model=ReporteDevoluciones)
def returns_report(
    current_user: ReportReader,
    db: Annotated[Session, Depends(get_db)],
    branch_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> ReporteDevoluciones:
    return ReportService(db).returns(
        user=current_user,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
    )
