# backend/app/routers/tips.py
#
# POST /api/tips/personalized
# Returns up to 5 personalised carbon reduction tips based on the user's
# footprint breakdown. Pure in-process computation — no DB or external API.
#
# [SECURITY] Rate limited to prevent automated scraping and CPU exhaustion.
# The ML predictor generates tips in O(1) time, but an unbounded endpoint is
# still an easy amplification target for scripted callers.

from typing import List

from fastapi import APIRouter, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.models.schemas import CategoryBreakdown, Tip
from app.services.ml_predictor import generate_tips

router = APIRouter()
settings = get_settings()

# [SECURITY] Per-IP rate limiter — sourced from RATE_LIMIT_CALCULATE ("30/minute").
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/personalized",
    response_model=List[Tip],
    status_code=status.HTTP_200_OK,
    summary="Get personalised carbon reduction tips",
    description=(
        "Returns up to 5 actionable tips ranked by estimated annual CO2e savings. "
        "Pure computation — no external API call. Rate limited."
    ),
)
# [SECURITY] 30/minute per IP prevents scripted scraping of tip generation.
@limiter.limit(settings.RATE_LIMIT_CALCULATE)
def get_tips(request: Request, breakdown: CategoryBreakdown) -> List[Tip]:
    """
    Returns actionable tips for the highest-impact emission categories.
    [SECURITY] request parameter required by slowapi for rate-key extraction.
    """
    return generate_tips(breakdown)
