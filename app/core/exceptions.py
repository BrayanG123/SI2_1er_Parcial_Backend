"""Excepciones de aplicación y sus manejadores HTTP."""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger(__name__)


class AppException(Exception):
    """Error controlado que puede exponerse de forma segura por la API."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class DatabaseUnavailableError(AppException):
    """Indica que FastAPI está vivo, pero PostgreSQL no está disponible."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="database_unavailable",
            message="La API está disponible, pero no puede conectarse a PostgreSQL.",
            details={"api": "ok", "database": "unavailable"},
        )


class NotFoundError(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message=message,
        )


class ConflictError(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code="conflict",
            message=message,
        )


class AuthenticationError(AppException):
    def __init__(self, message: str = "Credenciales o token inválidos.") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="authentication_required",
            message=message,
        )


class ForbiddenError(AppException):
    def __init__(self, message: str = "No tienes permisos para realizar esta acción.") -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="forbidden",
            message=message,
        )


class ConfigurationError(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="configuration_error",
            message=message,
        )


def _error_content(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": jsonable_encoder(details),
        }
    }


async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_content(exc.code, exc.message, exc.details),
    )


async def http_exception_handler(
    _request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "La solicitud no pudo procesarse."
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_content("http_error", message, exc.detail),
        headers=exc.headers,
    )


async def validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_content(
            "validation_error",
            "Los datos enviados no son válidos.",
            exc.errors(),
        ),
    )


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no controlado en %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_content(
            "internal_error",
            "Ocurrió un error interno. Inténtalo nuevamente.",
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra un contrato uniforme para errores controlados y no controlados."""
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unexpected_exception_handler)
