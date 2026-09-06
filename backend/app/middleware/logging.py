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


class RequestLoggingMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:

        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response