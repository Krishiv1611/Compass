"""
Token-bucket rate limiter middleware.

Limits requests per user (identified by JWT) to prevent abuse.
Anonymous requests (no valid JWT) share a global bucket.
"""

import time
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from jose import JWTError

logger = logging.getLogger(__name__)

# Configuration
MAX_REQUESTS = 60  # max requests per window
WINDOW_SECONDS = 60  # window size in seconds


class _TokenBucket:
    """Simple per-key token-bucket rate limiter."""

    def __init__(
        self,
        max_requests: int = MAX_REQUESTS,
        window: int = WINDOW_SECONDS,
        clock=time.time,
    ):
        self.max_requests = max_requests
        self.window = window
        self.clock = clock
        self._buckets: dict[str, list[float]] = {}

    def _prune(self) -> None:
        now = self.clock()
        for key, timestamps in list(self._buckets.items()):
            kept = [timestamp for timestamp in timestamps if now - timestamp < self.window]
            if kept:
                self._buckets[key] = kept
            else:
                del self._buckets[key]

    def is_allowed(self, key: str, *, weight: int = 1) -> bool:
        """Check if a request from `key` is allowed."""
        self._prune()
        now = self.clock()
        bucket = self._buckets.setdefault(key, [])

        if len(bucket) + weight > self.max_requests:
            return False

        bucket.extend([now] * weight)
        return True

    def remaining(self, key: str) -> int:
        """Return remaining requests in the current window."""
        self._prune()
        return max(0, self.max_requests - len(self._buckets.get(key, [])))


_limiter = _TokenBucket()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that rate-limits by user ID (from JWT) or client IP.

    Skips rate limiting for health check and docs endpoints.
    """

    # Paths exempt from rate limiting
    EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}
    ENDPOINT_WEIGHTS = {
        "/api/auth": 3,
        "/api/uploads": 5,
        "/api/workspaces/import": 5,
        "/api/chat/send": 3,
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Determine the rate-limit key
        key = self._get_key(request)

        weight = self._weight_for(request.url.path)
        if not _limiter.is_allowed(key, weight=weight):
            logger.warning(f"Rate limit exceeded for key={key}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(_limiter.remaining(key))
        return response

    @classmethod
    def _weight_for(cls, path: str) -> int:
        for prefix, weight in cls.ENDPOINT_WEIGHTS.items():
            if path.startswith(prefix):
                return weight
        return 1

    @staticmethod
    def _get_key(request: Request) -> str:
        """Extract user ID from Authorization header, or fall back to client IP."""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                from backend.auth.jwt import decode_token

                payload = decode_token(token)
                return f"user:{payload.get('sub', 'unknown')}"
            except (JWTError, Exception):
                pass

        # Fallback to IP
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
