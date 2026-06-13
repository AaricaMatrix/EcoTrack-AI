from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.config import get_settings
from app.core.database import engine, Base
from app.routers import auth, carbon, predictions, tips, insights

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
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS.split(","),
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

@app.get("/api/test-env")
async def test_env():
    import os
    gemini_key = os.getenv("GEMINI_API_KEY", "NOT SET")
    return {
        "gemini_key_set": gemini_key != "NOT SET",
        "gemini_key_preview": gemini_key[:10] + "..." if gemini_key != "NOT SET" else "NOT SET"
    }
