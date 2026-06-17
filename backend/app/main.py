# backend/app/main.py
# Production-grade FastAPI entry point with strict CORS, security headers, rate limiting

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.config import get_settings
from app.core.database import engine, Base
from app.routers import auth, carbon, predictions, tips, insights, community

settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title=settings.APP_NAME,
    description="Carbon Footprint Awareness Platform with ML Trend Predictions",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    return response

# CORS — specific origins from environment, not wildcard
# Falls back to common dev origins if env var not set
ALLOWED_ORIGINS = settings.ALLOWED_ORIGINS.split(",") if settings.ALLOWED_ORIGINS else [
    "https://eco-track-ai-three.vercel.app",
    "http://localhost:5173",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,        # Strict allowlist — never wildcard in prod
    allow_credentials=True,               # Allow Authorization header
    allow_methods=["GET", "POST"],        # Only methods the API actually uses
    allow_headers=["Authorization", "Content-Type"],  # Explicit header allowlist
)

app.include_router(auth.router,        prefix="/api/auth",        tags=["Authentication"])
app.include_router(carbon.router,      prefix="/api/carbon",      tags=["Carbon"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["ML Predictions"])
app.include_router(tips.router,        prefix="/api/tips",        tags=["Tips"])
app.include_router(insights.router,    prefix="/api/insights",    tags=["AI Insights"])

@app.get("/", tags=["Health"], include_in_schema=False)
async def root():
    return {"status": "running", "app": settings.APP_NAME, "version": settings.APP_VERSION}

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}