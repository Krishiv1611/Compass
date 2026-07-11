"""
Structured request/response logging middleware.

Logs each request with method, path, status code, duration, and user ID.
"""

import time
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("backend.access")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with timing and user context."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()

        # Extract user hint from Authorization header (non-blocking, best effort)
        user_id = "-"
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from backend.auth.jwt import decode_token

                payload = decode_token(auth_header[7:])
                user_id = payload.get("sub", "-")
            except Exception:
                user_id = "invalid-token"

        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "%s %s %d %.1fms user=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            user_id,
        )

        response.headers["X-Request-Duration-Ms"] = f"{duration_ms:.1f}"
        return response
