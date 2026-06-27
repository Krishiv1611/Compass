"""
Token-bucket rate limiter middleware.

Limits requests per user (identified by JWT) to prevent abuse.
Anonymous requests (no valid JWT) share a global bucket.
"""

import time
import logging
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from jose import JWTError

logger = logging.getLogger(__name__)

# Configuration
MAX_REQUESTS = 60        # max requests per window
WINDOW_SECONDS = 60      # window size in seconds


class _TokenBucket:
    """Simple per-key token-bucket rate limiter."""

    def __init__(self, max_requests: int = MAX_REQUESTS, window: int = WINDOW_SECONDS):
        self.max_requests = max_requests
        self.window = window
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        """Check if a request from `key` is allowed."""
        now = time.time()
        bucket = self._buckets[key]

        # Remove expired timestamps
        self._buckets[key] = [ts for ts in bucket if now - ts < self.window]
        bucket = self._buckets[key]

        if len(bucket) >= self.max_requests:
            return False

        bucket.append(now)
        return True

    def remaining(self, key: str) -> int:
        """Return remaining requests in the current window."""
        now = time.time()
        bucket = [ts for ts in self._buckets.get(key, []) if now - ts < self.window]
        return max(0, self.max_requests - len(bucket))


_limiter = _TokenBucket()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that rate-limits by user ID (from JWT) or client IP.

    Skips rate limiting for health check and docs endpoints.
    """

    # Paths exempt from rate limiting
    EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Determine the rate-limit key
        key = self._get_key(request)

        if not _limiter.is_allowed(key):
            logger.warning(f"Rate limit exceeded for key={key}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(_limiter.remaining(key))
        return response

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
