import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

logger = logging.getLogger("devops_monitor")


class APIError(Exception):
    """Base API error class."""
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(APIError):
    """Resource not found error."""
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_404_NOT_FOUND, details)


class UnauthorizedError(APIError):
    """Unauthorized access error."""
    def __init__(self, message: str = "Unauthorized access", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED, details)


class ForbiddenError(APIError):
    """Forbidden access error."""
    def __init__(self, message: str = "Access forbidden", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_403_FORBIDDEN, details)


class APIValidationError(APIError):
    """Validation error."""
    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class ConflictError(APIError):
    """Conflict error."""
    def __init__(self, message: str = "Resource conflict", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_409_CONFLICT, details)


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle custom API errors."""
    logger.error(f"API Error: {exc.message} - Details: {exc.details}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.message,
            "details": exc.details,
            "status_code": exc.status_code,
        }
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle FastAPI validation errors."""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": True,
            "message": "Validation failed",
            "details": {"errors": exc.errors()},
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions."""
    logger.warning(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.exception(f"Unexpected error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "message": "An unexpected error occurred",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        }
    )