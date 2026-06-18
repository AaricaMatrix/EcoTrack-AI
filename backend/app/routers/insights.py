# backend/app/routers/insights.py
#
# Three AI-powered endpoints:
#   POST /api/insights/analyze  — LLM generates personalised narrative analysis
#   POST /api/insights/anomaly  — Isolation Forest flags unusual emission spikes
#   POST /api/insights/chat     — Multi-turn EcoBot chatbot powered by LLM
#
# [SECURITY] Rate limiting is applied to ALL three endpoints to prevent:
#   • LLM cost exhaustion (LPDoS) — unlimited free calls would drain the API quota
#   • Brute-force prompt injection attempts via the chat endpoint
#   • Abusive scraping of AI-generated insights
#
# The limit is sourced from settings.RATE_LIMIT_AI (default "20/minute") so it
# can be tightened in production via environment variable without code changes.

import logging

from fastapi import APIRouter, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.models.schemas import (
    InsightRequest, InsightResponse,
    AnomalyRequest, AnomalyResult,
    ChatRequest, ChatResponse,
)
from app.services.ai_insights import generate_insights, chat_with_ecobot
from app.services.anomaly_detector import detect_anomaly

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# [SECURITY] Use the same Limiter key function (remote IP) as the global limiter.
# A dedicated limiter instance is used here so AI endpoints can have a stricter
# rate limit than the global default without touching main.py.
limiter = Limiter(key_func=get_remote_address)


# ── POST /api/insights/analyze ────────────────────────────────────────────────

@router.post(
    "/analyze",
    response_model=InsightResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate AI-powered personalised carbon footprint analysis",
    description=(
        "Sends the user's footprint breakdown to the LLM which returns a structured "
        "natural-language analysis: summary, dominant category, key non-obvious insight, "
        "3-step action plan, and a motivational closing statement. "
        "Falls back gracefully if the API is unavailable. "
        "Rate limited to prevent cost exhaustion."
    ),
)
# [SECURITY] Rate limit: 20 requests/minute per IP.
# Prevents a single attacker from exhausting the GROQ API quota.
@limiter.limit(settings.RATE_LIMIT_AI)
async def analyze(request: Request, req: InsightRequest) -> InsightResponse:
    """
    LLM reads the exact kg CO₂e numbers and generates a personalised narrative.
    Unlike hardcoded tips, this adapts to every possible combination of inputs.
    Async because it awaits the external LLM API HTTP call.

    [SECURITY] request parameter is required by slowapi for rate-key extraction.
    """
    return await generate_insights(req)


# ── POST /api/insights/anomaly ────────────────────────────────────────────────

@router.post(
    "/anomaly",
    response_model=AnomalyResult,
    status_code=status.HTTP_200_OK,
    summary="Detect anomalous emission spikes using Isolation Forest ML",
    description=(
        "Trains an Isolation Forest on the user's personal emission history "
        "and evaluates whether the current reading is a statistical outlier. "
        "Returns per-category z-scores and a human-readable explanation. "
        "Requires at least 3 historical records. Rate limited."
    ),
)
# [SECURITY] Rate limit: same budget as other AI endpoints.
# Although this runs locally (no external API), the Isolation Forest fit is
# CPU-bound and could be abused for compute exhaustion.
@limiter.limit(settings.RATE_LIMIT_AI)
def anomaly(request: Request, req: AnomalyRequest) -> AnomalyResult:
    """
    Synchronous — Isolation Forest runs in-process, no external API call needed.
    Uses the user's own history as the baseline, not a global threshold.

    [SECURITY] request parameter required by slowapi for rate-key extraction.
    """
    return detect_anomaly(req)


# ── POST /api/insights/chat ───────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with EcoBot — AI carbon coach",
    description=(
        "Multi-turn conversational endpoint. Send the full conversation history "
        "and optionally the user's footprint breakdown for context-aware answers. "
        "EcoBot answers questions about emissions, reduction strategies, and the "
        "user's specific data. Falls back gracefully if API is unavailable. "
        "Rate limited to prevent prompt-injection abuse and cost exhaustion."
    ),
)
# [SECURITY] Rate limit: 20/minute per IP.
# Chat endpoints are a prime target for prompt injection via automated scripts.
# The rate limit adds a time-cost barrier to such attacks.
@limiter.limit(settings.RATE_LIMIT_AI)
async def chat(request: Request, req: ChatRequest) -> ChatResponse:
    """
    LLM maintains conversation context via the messages history array.
    The user's footprint is injected into the system prompt so EcoBot can
    give personalised answers.

    [SECURITY] request parameter required by slowapi for rate-key extraction.
    """
    return await chat_with_ecobot(req)
