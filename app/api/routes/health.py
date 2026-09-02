from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import DatabaseUnavailableError
from app.db.session import get_db


router = APIRouter(prefix="/health", tags=["health"])


class ServiceStatuses(BaseModel):
    api: Literal["ok"]
    database: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ok"]
    environment: str
    services: ServiceStatuses


@router.get("", response_model=ReadinessResponse)
def readiness_check(db: Session = Depends(get_db)) -> ReadinessResponse:
    """Comprueba que la API puede ejecutar una consulta mínima en PostgreSQL."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise DatabaseUnavailableError() from exc

    settings = get_settings()
    return ReadinessResponse(
        status="ok",
        environment=settings.app_env,
        services=ServiceStatuses(api="ok", database="ok"),
    )
