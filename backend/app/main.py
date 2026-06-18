# backend/app/main.py
# Production-grade FastAPI entry point with strict CORS, security headers,
# rate limiting, and startup secret validation.

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.database import engine, Base
from app.routers import auth, carbon, predictions, tips, insights, community

logger = logging.getLogger(__name__)

# [SECURITY] get_settings() is called at module import time.
# The Settings model_validator will raise ValueError and abort startup if:
#   • SECRET_KEY is missing or set to a known placeholder
#   • DEBUG=True is set in a detected production environment
# This ensures misconfigured deployments fail loudly at boot, not silently at runtime.
settings = get_settings()

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: create DB tables on startup.
    Any startup failure here will prevent the server from accepting requests.
    """
    Base.metadata.create_all(bind=engine)
    logger.info("startup: database tables verified / created")
    yield
    logger.info("shutdown: application stopping")


# [SECURITY] Disable OpenAPI docs in non-DEBUG mode to reduce attack surface.
# Docs are still accessible in development (DEBUG=True) for convenience.
app = FastAPI(
    title=settings.APP_NAME,
    description="Carbon Footprint Awareness Platform with ML Trend Predictions",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# [SECURITY] Global handler for unhandled exceptions.
# FastAPI's default 500 response includes a Python traceback in DEBUG mode
# and a generic 'Internal Server Error' string in production.  Neither is
# structured JSON.  This handler guarantees a consistent, opaque JSON body
# so callers never see stack frames, file paths, or DB error messages.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled exception on %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    """
    Attach security headers to every HTTP response.

    [SECURITY] Headers applied:
    • Content-Security-Policy — restricts sources for scripts, styles, images.
      Prevents XSS by blocking inline scripts and unauthorised external resources.
    • X-Frame-Options — blocks this API from being embedded in an iframe (clickjacking).
    • X-Content-Type-Options — prevents MIME-type sniffing.
    • Referrer-Policy — limits referer header exposure on cross-origin requests.
    • Strict-Transport-Security — enforces HTTPS for 2 years, including subdomains.
    • Permissions-Policy — disables geolocation and microphone access.
    """
    response = await call_next(request)

    # [SECURITY] CSP — API-only server; no browser rendering expected.
    # default-src 'none' blocks everything not explicitly permitted.
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'"
    )
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


# [SECURITY] CORS — explicit allowlist from environment, never wildcard.
# An empty ALLOWED_ORIGINS string means no cross-origin requests are permitted,
# which is the safe default for a purely backend API.
ALLOWED_ORIGINS = (
    [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
    if settings.ALLOWED_ORIGINS
    else []
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],       # only methods the API uses
    allow_headers=["Authorization", "Content-Type"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,        prefix="/api/auth",        tags=["Authentication"])
app.include_router(carbon.router,      prefix="/api/carbon",      tags=["Carbon"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["ML Predictions"])
app.include_router(tips.router,        prefix="/api/tips",        tags=["Tips"])
app.include_router(insights.router,    prefix="/api/insights",    tags=["AI Insights"])
app.include_router(community.router,   prefix="/api/community",   tags=["Community"])


# ── Health endpoints ──────────────────────────────────────────────────────────

@app.get("/", tags=["Health"], include_in_schema=False)
async def root() -> dict:
    """
    Root endpoint returning basic application status.
    """
    # [SECURITY] Do not expose version string in production health checks.
    return {"status": "running", "app": settings.APP_NAME}


@app.get("/health", tags=["Health"])
async def health() -> dict:
    """
    Health check endpoint.
    """
    return {"status": "healthy"}