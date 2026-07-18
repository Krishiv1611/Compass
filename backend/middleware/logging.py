"""
Structured request/response logging middleware.

Logs each request with method, path, status code, duration, and user ID.
"""

import time
import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger("backend.access")

class LoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with timing and user context as JSON."""

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

        # Bind context to the logger
        log = logger.bind(
            method=request.method,
            path=request.url.path,
            user_id=user_id,
            client_ip=request.client.host if request.client else "unknown"
        )

        try:
            response: Response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            
            log.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2)
            )
            response.headers["X-Request-Duration-Ms"] = f"{duration_ms:.1f}"
            return response
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            log.error(
                "request_failed",
                error=str(e),
                duration_ms=round(duration_ms, 2)
            )
            raise
