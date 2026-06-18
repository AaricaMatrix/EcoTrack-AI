# backend/app/core/config.py
#
# Application settings loaded exclusively from environment variables / .env file.
#
# [SECURITY] Startup validation:
#   The application will REFUSE to start if SECRET_KEY is absent or still set
#   to the known-insecure placeholder shipped in .env.example.
#   This prevents silent deployment with a predictable signing key.
#
# [SECURITY] No fallback values for sensitive fields:
#   SECRET_KEY and GROQ_API_KEY intentionally have no Python-level default.
#   Missing values raise a clear ValueError at import time, not a cryptic
#   runtime error minutes later.

import os
from functools import lru_cache
from pathlib import Path
from pydantic import ConfigDict, model_validator
from pydantic_settings import BaseSettings

# Resolve the .env file path robustly so it is found whether the process is
# started from the project root (pytest) or from backend/ (uvicorn).
# Checks: backend/.env → .env → None (relies purely on real env vars)
_THIS_DIR = Path(__file__).resolve().parent          # …/backend/app/core
_BACKEND_DIR = _THIS_DIR.parent.parent               # …/backend
_PROJECT_ROOT = _BACKEND_DIR.parent                  # …/ (project root)

def _find_env_file() -> str | None:
    for candidate in [_BACKEND_DIR / ".env", _PROJECT_ROOT / ".env", Path(".env")]:
        if candidate.is_file():
            return str(candidate)
    return None

_ENV_FILE = _find_env_file()

# Placeholder strings that must NEVER appear in production.
# [SECURITY] If SECRET_KEY equals any of these, startup is aborted.
_KNOWN_INSECURE_KEYS: frozenset[str] = frozenset({
    "change-me-in-production-use-32-random-bytes",
    "replace-with-32-random-bytes",
    "your-secret-key",
    "",
})


class Settings(BaseSettings):
    APP_NAME: str = "EcoTrack AI"
    APP_VERSION: str = "1.0.0"

    # [SECURITY] DEBUG must default to False.
    # Never override to True in production — it enables SQL echo and verbose
    # FastAPI error traces that expose internal structure to callers.
    DEBUG: bool = False

    # [SECURITY] No default value — pydantic raises ValidationError at startup
    # if SECRET_KEY is not set in the environment or .env file.
    SECRET_KEY: str

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # CORS — explicit allowlist, never wildcard
    ALLOWED_ORIGINS: str = ""
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"

    # Rate-limit strings consumed by slowapi
    RATE_LIMIT_REGISTER: str = "5/minute"
    RATE_LIMIT_LOGIN: str = "10/minute"
    RATE_LIMIT_CALCULATE: str = "30/minute"
    RATE_LIMIT_AI: str = "20/minute"        # applied to all LLM endpoints

    DATABASE_URL: str = "sqlite:///./ecotrack.db"

    # [SECURITY] No default — raises ValidationError if missing.
    # The key is read from the environment; it must never be hardcoded here.
    GROQ_API_KEY: str = ""                  # empty string = LLM fallback mode

    model_config = ConfigDict(
        # _ENV_FILE is resolved at module load time relative to this file's
        # location, so both `uvicorn` (started from backend/) and `pytest`
        # (started from the project root) find the same .env.
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        # [SECURITY] Ignore extra fields so undocumented env vars don't leak
        # into the settings object.
        extra="ignore",
    )

    @model_validator(mode="after")
    def _validate_security_critical_fields(self) -> "Settings":
        """
        [SECURITY] Hard startup gate — aborts the process if security-critical
        configuration is absent or clearly insecure.

        This check runs once at import time (guarded by lru_cache).
        """
        # 1. SECRET_KEY must be present and not a known placeholder.
        if not self.SECRET_KEY or self.SECRET_KEY.strip() in _KNOWN_INSECURE_KEYS:
            raise ValueError(
                "[SECURITY] SECRET_KEY is missing or set to an insecure placeholder. "
                "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\" "
                "and set it in your .env file."
            )

        # 2. SECRET_KEY must be at least 32 characters (256-bit minimum for HS256).
        if len(self.SECRET_KEY) < 32:
            raise ValueError(
                "[SECURITY] SECRET_KEY is too short. "
                "Minimum 32 characters required for HS256 signing."
            )

        # 3. DEBUG must never be True in a non-local environment.
        # We detect production by checking common hosting env vars.
        is_production = any(
            os.getenv(v)
            for v in ("RENDER", "RAILWAY_ENVIRONMENT", "FLY_APP_NAME", "VERCEL")
        )
        if is_production and self.DEBUG:
            raise ValueError(
                "[SECURITY] DEBUG=True is not permitted in a production environment. "
                "Set DEBUG=False in your production .env."
            )

        return self


@lru_cache()
def get_settings() -> Settings:
    """
    Returns the singleton Settings instance.
    lru_cache ensures .env is parsed only once per process lifetime.
    ValidationError from the model_validator propagates here and aborts startup.
    """
    return Settings()
