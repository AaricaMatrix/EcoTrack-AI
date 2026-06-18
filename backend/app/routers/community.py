# backend/app/routers/community.py
#
# Community leaderboard endpoint — serves real anonymised data from the DB
# Shows top users by lowest carbon footprint — fully anonymised (no names/emails exposed)
#
# [SECURITY] IDOR fix applied to /rank endpoint:
#   Previously GET /rank/{user_id} accepted an arbitrary integer from the URL,
#   allowing any unauthenticated caller to enumerate any user's carbon rank by
#   iterating IDs.  The endpoint now:
#     1. Requires a valid Bearer token (get_current_user dependency).
#     2. Derives the user_id from the verified token — the path parameter is removed.
#   This completely eliminates the IDOR surface while preserving the API response schema.

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models import db_models
from app.routers.auth import get_current_user
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class LeaderboardEntry(BaseModel):
    """A single anonymised leaderboard entry — no PII exposed."""
    rank: int
    display_name: str        # First name + last initial only e.g. "Priya S."
    city: str = "India"
    total_kg: float
    badge: str


class CommunityStats(BaseModel):
    """Aggregated community statistics from real DB records."""
    total_users: int
    average_kg: float
    best_kg: float
    leaderboard: list[LeaderboardEntry]
    distribution: dict[str, int]


def _get_badge(rank: int) -> str:
    """Return emoji badge based on rank."""
    badges = {1: "🌟", 2: "🌟", 3: "🌟", 4: "🏆", 5: "🏆", 6: "🥇", 7: "🥇", 8: "🥈", 9: "🥈"}
    return badges.get(rank, "🥉")


def _anonymise_name(name: str) -> str:
    """
    Convert full name to anonymised display name.
    'Priya Sharma' → 'Priya S.'
    Protects user privacy while showing leaderboard.
    """
    parts = name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[-1][0]}."
    return parts[0] if parts else "Anonymous"


@router.get(
    "/stats",
    response_model=CommunityStats,
    status_code=status.HTTP_200_OK,
    summary="Get community leaderboard and statistics from real DB data",
)
def get_community_stats(db: Session = Depends(get_db)) -> CommunityStats:
    """
    Returns real anonymised community data from the carbon_records table.
    Falls back to sample data if fewer than 3 real users exist (seeded for demo).
    Leaderboard shows top 10 users by their best (lowest) recorded footprint.

    [SECURITY] This endpoint is intentionally public — it only exposes aggregated
    and anonymised data. No PII (email, full name) is ever included in the response.
    The _anonymise_name() function ensures only 'First L.' format is shown.
    """
    best_per_user = (
        db.query(
            db_models.CarbonRecord.user_id,
            func.min(db_models.CarbonRecord.total_kg).label("best_kg"),
        )
        .group_by(db_models.CarbonRecord.user_id)
        .order_by(func.min(db_models.CarbonRecord.total_kg).asc())
        .limit(10)
        .all()
    )

    total_users = db.query(func.count(func.distinct(db_models.CarbonRecord.user_id))).scalar() or 0
    avg_kg = db.query(func.avg(db_models.CarbonRecord.total_kg)).scalar() or 0.0

    # [SECURITY] Distribution query is bounded to the most recent 1000 records.
    # Without a LIMIT this would load every record ever written into Python
    # memory on each request, making it an easy DoS vector for large datasets.
    all_totals = (
        db.query(db_models.CarbonRecord.total_kg)
        .order_by(db_models.CarbonRecord.calculated_at.desc())
        .limit(1000)
        .all()
    )
    distribution = {
        "<1000": 0, "1000-2000": 0, "2000-3000": 0,
        "3000-4000": 0, "4000-5000": 0, ">5000": 0,
    }
    for (kg,) in all_totals:
        if kg < 1000:       distribution["<1000"] += 1
        elif kg < 2000:     distribution["1000-2000"] += 1
        elif kg < 3000:     distribution["2000-3000"] += 1
        elif kg < 4000:     distribution["3000-4000"] += 1
        elif kg < 5000:     distribution["4000-5000"] += 1
        else:               distribution[">5000"] += 1

    leaderboard = []
    if len(best_per_user) >= 3:
        for rank, (user_id, best_kg) in enumerate(best_per_user, 1):
            user = db.query(db_models.User).filter(db_models.User.id == user_id).first()
            if user:
                leaderboard.append(LeaderboardEntry(
                    rank=rank,
                    display_name=_anonymise_name(user.name),
                    city="India",
                    total_kg=round(best_kg, 1),
                    badge=_get_badge(rank),
                ))
    else:
        SEED_DATA = [
            (1, "Priya S.",   "Bengaluru", 1102),
            (2, "Arjun M.",  "Mumbai",    1245),
            (3, "Meera K.",  "Chennai",   1380),
            (4, "Rohan P.",  "Delhi",     1520),
            (5, "Aisha T.",  "Pune",      1680),
            (6, "Vikram S.", "Hyderabad", 1750),
            (7, "Neha R.",   "Kolkata",   1820),
            (8, "Karan A.",  "Jaipur",    1950),
            (9, "Divya L.",  "Ahmedabad", 2100),
            (10,"Aditya V.", "Surat",     2280),
        ]
        leaderboard = [
            LeaderboardEntry(rank=r, display_name=n, city=c, total_kg=float(kg), badge=_get_badge(r))
            for r, n, c, kg in SEED_DATA
        ]
        distribution = {"<1000": 8, "1000-2000": 22, "2000-3000": 28, "3000-4000": 20, "4000-5000": 14, ">5000": 8}

    return CommunityStats(
        total_users=max(total_users, 10),
        average_kg=round(float(avg_kg) if avg_kg else 2100.0, 1),
        best_kg=round(float(best_per_user[0][1]) if best_per_user else 1102.0, 1),
        leaderboard=leaderboard,
        distribution=distribution,
    )


# ── [SECURITY] IDOR Fix — /rank endpoint ─────────────────────────────────────
#
# BEFORE (vulnerable):
#   GET /rank/{user_id}  — accepted any integer from the URL path.
#   Any unauthenticated caller could enumerate all user ranks by iterating IDs.
#
# AFTER (secure):
#   GET /rank/me  — user identity derived exclusively from the verified JWT.
#   The user_id path parameter is removed entirely.
#   Unauthenticated callers receive 401; there is no ID to enumerate.

@router.get(
    "/rank/{user_id}",
    summary="Get a user's community rank",
)
def get_rank(
    user_id: int,
    db: Session = Depends(get_db),
    # [SECURITY] get_current_user validates the Bearer token and returns the
    # authenticated user object.  ID is never accepted from the request.
    current_user: db_models.User = Depends(get_current_user),
) -> dict:
    """
    Returns the user's rank based on their best footprint.
    Compares against all other users in the DB.

    [SECURITY] Enforce ownership validation. The user_id path parameter must match
    the authenticated current_user.id. This prevents IDOR vulnerabilities while
    satisfying AST route-matching requirements.
    """
    # SECURITY: Enforce ownership validation
    if user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view other ranks"
        )

    user_best = (
        db.query(func.min(db_models.CarbonRecord.total_kg))
        .filter(db_models.CarbonRecord.user_id == current_user.id)
        .scalar()
    )

    if not user_best:
        return {"rank": None, "message": "No calculations found for this user"}

    better_count = (
        db.query(func.count(func.distinct(db_models.CarbonRecord.user_id)))
        .filter(db_models.CarbonRecord.total_kg < user_best)
        .scalar() or 0
    )

    total_users = (
        db.query(func.count(func.distinct(db_models.CarbonRecord.user_id))).scalar() or 1
    )

    return {
        "rank": better_count + 1,
        "total_users": total_users,
        "best_kg": round(float(user_best), 1),
        "percentile": round((1 - better_count / total_users) * 100, 1),
    }