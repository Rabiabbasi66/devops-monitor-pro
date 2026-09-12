import logging
import sys
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("devops_monitor")


def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Hide noisy MongoDB/PyMongo DEBUG logs
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("pymongo.topology").setLevel(logging.WARNING)
    logging.getLogger("pymongo.connection").setLevel(logging.WARNING)

    # Hide Uvicorn access logs because our middleware handles requests
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    # Set HTTP library logging to WARNING
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


class RequestLoggingMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:

        start = time.perf_counter()
        
        # Log request details (without sensitive data)
        client_host = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        
        # Mask sensitive paths in logs
        if "/auth/" in path or "/login" in path or "/register" in path:
            path = "/auth/[masked]"

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000

        # Log with structured format
        logger.info(
            "%s %s -> %s (%.1fms) | client: %s",
            method,
            path,
            response.status_code,
            duration_ms,
            client_host,
        )

        # Log slow requests (> 1 second)
        if duration_ms > 1000:
            logger.warning(
                "Slow request detected: %s %s (%.1fms)",
                method,
                path,
                duration_ms,
            )

        # Log error responses
        if response.status_code >= 400:
            logger.warning(
                "Error response: %s %s -> %s (%.1fms)",
                method,
                path,
                response.status_code,
                duration_ms,
            )

        return response