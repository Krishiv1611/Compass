"""
Compass — FastAPI Backend Application.

Main entry point for the web API. Includes:
  - CORS middleware
  - Rate limiting & structured logging middleware
  - Auth, sessions, chat, tools, and settings routers
  - Health check endpoint
  - Global exception handlers
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import text

from backend.config import settings
from backend.db import engine

import structlog
import sys

import logging

# ── Configure structlog ────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger(__name__)


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    logger.info("Starting Compass backend...")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified ✓")
    except Exception as exc:
        logger.error(f"Database connection failed: {exc}")
        
    yield

    # Shutdown
    logger.info("Shutting down Compass backend...")
    engine.dispose()


# ── Create FastAPI app ───────────────────────────────────────────────────────────

app = FastAPI(
    title="Compass API",
    description="AI coding assistant backend — auth, sessions, chat, and tools.",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Middleware (order matters — last added = first executed) ──────────────────────

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Request logging
from backend.middleware.logging import LoggingMiddleware
from backend.middleware.rate_limit import RateLimitMiddleware

app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware)


# ── Exception handlers ───────────────────────────────────────────────────────────


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors with a clean 422 response."""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions — return 500 with a safe message."""
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Health check ─────────────────────────────────────────────────────────────────


@app.get("/health", tags=["system"])
def health_check():
    """Health check endpoint for monitoring and load balancers."""
    return {"status": "ok", "service": "compass-api"}


# ── Register routers ─────────────────────────────────────────────────────────────

from backend.routers.auth import router as auth_router
from backend.routers.sessions import router as sessions_router
from backend.routers.chat import router as chat_router
from backend.routers.core import router as core_router
from backend.routers.uploads import router as uploads_router
from backend.routers.workspaces import router as workspaces_router

# Set up routers
app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(chat_router)
app.include_router(core_router)
app.include_router(uploads_router)
app.include_router(workspaces_router)
