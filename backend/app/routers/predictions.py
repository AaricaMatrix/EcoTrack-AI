# backend/app/routers/predictions.py
#
# POST /api/predictions/forecast
# ─────────────────────────────────────────────────────────────────────────────
# Open to all callers (no auth required).
# When a valid JWT is supplied, historical records are used to improve the
# ML forecast quality.  Invalid / expired tokens are silently ignored —
# the request is treated as anonymous rather than returning an error.
#
# [SECURITY] Rate limited — this endpoint is CPU-bound (Ridge regression) and
# DB-backed (history lookup). Anonymous access makes it a DoS target without
# a rate limit. Limit sourced from settings.RATE_LIMIT_CALCULATE ("30/minute").

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import db_models
from app.models.schemas import CategoryBreakdown, PredictionResult
from app.services.ml_predictor import predict_future_footprint

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# [SECURITY] Dedicated limiter for this router. Uses the same remote-IP key
# function as the global limiter so limits are counted per caller IP.
limiter = Limiter(key_func=get_remote_address)

def get_optional_token(request: Request) -> Optional[str]:
    """
    Passively extract the Bearer token without ever raising an HTTP 401.
    This guarantees anonymous callers can access the endpoint regardless of
    FastAPI/Starlette version differences in OAuth2PasswordBearer.
    """
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None

# ── Constants ─────────────────────────────────────────────────────────────────
# Maximum records fetched per user.  Caps memory consumption and query time
# for users with a long history; the ML model only needs recent data.
_MAX_HISTORY_RECORDS = 100

# Sanity bounds for a valid annual kg CO2e total.
# Values outside this range are likely data errors or adversarial inputs.
_MIN_VALID_KG = 0.0
_MAX_VALID_KG = 100_000.0  # ~10× the heaviest realistic footprint


def _resolve_historical_totals(token: Optional[str], db: Session) -> Optional[list[float]]:
    """
    Attempt to load the authenticated user's recent carbon history.

    Returns a validated list of floats (≥3 entries) when successful,
    or None when the token is absent, invalid, or the user has too few records.

    Security notes:
    ─────────────────────────────────────────────────────────────────────────
    • decode_access_token() already catches JWTError internally and returns
      None, so expired / tampered tokens surface as None here — never 500.
    • The DB query is bounded by _MAX_HISTORY_RECORDS to prevent an attacker
      with a long-lived account from triggering unbounded memory allocation.
    • Only columns required by the ML model (total_kg) are fetched.
    • Data is validated before being passed to the ML model: nulls, negatives,
      and out-of-range values are dropped so the model always receives clean input.
    • All DB errors are caught and logged; the caller falls back to anonymous
      forecasting so no sensitive detail leaks through an exception.
    """
    # ── 1. No token supplied → anonymous mode ────────────────────────────────
    if not token:
        return None

    # ── 2. Decode JWT safely ──────────────────────────────────────────────────
    # decode_access_token returns None for invalid/expired tokens (never raises).
    email: Optional[str] = decode_access_token(token)
    if not email:
        # [SECURITY] Invalid or expired token — treat as anonymous, not an error.
        logger.debug("predictions/forecast: token present but could not be decoded; falling back to anonymous")
        return None

    try:
        # ── 3. Resolve user ───────────────────────────────────────────────────
        user = (
            db.query(db_models.User)
            .filter(db_models.User.email == email)
            .first()
        )
        if not user:
            return None

        # ── 4. Fetch recent records — bounded query ───────────────────────────
        # ORDER BY … DESC + LIMIT prevents loading the full table for active users.
        # We reverse in Python so the ML model receives chronological order.
        raw_records = (
            db.query(db_models.CarbonRecord.total_kg)
            .filter(db_models.CarbonRecord.user_id == user.id)
            .order_by(db_models.CarbonRecord.calculated_at.desc())
            .limit(_MAX_HISTORY_RECORDS)
            .all()
        )

        # ── 5. Validate & clean historical values ────────────────────────────
        # [SECURITY] Never pass raw DB floats directly to an ML model.
        # Filter out: None, NaN, negative, zero, and extreme outlier values.
        validated: list[float] = []
        for (kg,) in reversed(raw_records):   # chronological order for the model
            if kg is None:
                continue
            try:
                kg_f = float(kg)
            except (ValueError, TypeError):
                continue
            if kg_f != kg_f:            # NaN check (NaN != NaN is always True)
                continue
            if not (_MIN_VALID_KG < kg_f <= _MAX_VALID_KG):
                # Excludes zero, negative, and suspiciously large values.
                continue
            validated.append(kg_f)

        # ML model requires at least 3 data points to fit a trend curve.
        if len(validated) < 3:
            return None

        return validated

    except SQLAlchemyError as exc:
        # [SECURITY] Log the detail server-side; return None so the caller
        # degrades to anonymous mode without leaking DB internals.
        logger.warning("predictions/forecast: DB error resolving history: %s", exc)
        return None


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/forecast",
    response_model=PredictionResult,
    status_code=status.HTTP_200_OK,
    summary="Forecast 6-month carbon trajectory",
    description=(
        "Open to anonymous and authenticated callers. "
        "A valid Bearer token enables personalised ML forecasting using the "
        "user's own emission history. Rate limited."
    ),
)
# [SECURITY] 30 requests/minute per IP — matches RATE_LIMIT_CALCULATE.
# Prevents anonymous DoS via repeated ML inference + DB history lookups.
@limiter.limit(settings.RATE_LIMIT_CALCULATE)
def forecast(
    request: Request,                                          # required by slowapi
    breakdown: CategoryBreakdown,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(get_optional_token),
) -> PredictionResult:
    """
    Forecast the user's carbon footprint for the next 6 months.

    Anonymous callers receive a simulated baseline forecast.
    Authenticated callers with ≥3 historical records receive a personalised
    Ridge-regression forecast fitted to their real emission history.
    """
    # Resolve history (handles all auth/DB errors internally — never raises).
    historical_totals = _resolve_historical_totals(token, db)

    # Delegate to the ML service; errors here are genuine 500s and are not caught
    # here intentionally — FastAPI's global error handler will surface them.
    return predict_future_footprint(breakdown, historical_totals=historical_totals)
