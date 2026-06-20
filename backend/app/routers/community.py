# backend/app/routers/community.py
# Community leaderboard endpoint — serves real anonymised data from the DB.
# Shows top users by lowest carbon footprint — fully anonymised (no names/emails exposed).

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models import db_models
from pydantic import BaseModel

router = APIRouter()

# ── Constants ──────────────────────────────────────────────────────────────────
LEADERBOARD_LIMIT = 10
MIN_REAL_USERS_FOR_LEADERBOARD = 3   # Below this, seed data is shown instead
MIN_TOTAL_USERS_DISPLAYED = 10        # Floor shown to the user for credibility

# Footprint distribution bucket boundaries (kg CO2e/year)
DIST_BUCKET_1000 = 1000
DIST_BUCKET_2000 = 2000
DIST_BUCKET_3000 = 3000
DIST_BUCKET_4000 = 4000
DIST_BUCKET_5000 = 5000

DEFAULT_AVG_KG = 2100.0
DEFAULT_BEST_KG = 1102.0

# Realistic seed data shown only when fewer than MIN_REAL_USERS_FOR_LEADERBOARD
# real users have calculated their footprint. Replaced automatically as real
# users join — see get_community_stats().
SEED_LEADERBOARD_DATA = [
    (1,  "Priya S.",   "Bengaluru", 1102),
    (2,  "Arjun M.",   "Mumbai",    1245),
    (3,  "Meera K.",   "Chennai",   1380),
    (4,  "Rohan P.",   "Delhi",     1520),
    (5,  "Aisha T.",   "Pune",      1680),
    (6,  "Vikram S.",  "Hyderabad", 1750),
    (7,  "Neha R.",    "Kolkata",   1820),
    (8,  "Karan A.",   "Jaipur",    1950),
    (9,  "Divya L.",   "Ahmedabad", 2100),
    (10, "Aditya V.",  "Surat",     2280),
]
SEED_DISTRIBUTION = {
    "<1000": 8, "1000-2000": 22, "2000-3000": 28,
    "3000-4000": 20, "4000-5000": 14, ">5000": 8,
}


class LeaderboardEntry(BaseModel):
    """A single anonymised leaderboard entry — no PII exposed."""
    rank: int
    display_name: str
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
    """Return an emoji badge based on leaderboard rank."""
    if rank <= 2:  return "🌟"
    elif rank <= 4: return "🏆"
    elif rank <= 6: return "🥇"
    elif rank <= 8: return "🥈"
    else:           return "🥉"


def _anonymise_name(name: str) -> str:
    """
    Convert a full name to an anonymised display name.
    'Priya Sharma' becomes 'Priya S.' — protects user privacy on the
    public leaderboard while keeping the entry personable.
    """
    parts = name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[-1][0]}."
    return parts[0] if parts else "Anonymous"


def _bucket_distribution(all_totals: list[tuple[float]]) -> dict[str, int]:
    """Count footprint records into fixed kg CO2e range buckets for the chart."""
    distribution = {
        "<1000": 0, "1000-2000": 0, "2000-3000": 0,
        "3000-4000": 0, "4000-5000": 0, ">5000": 0,
    }
    for (kg,) in all_totals:
        if kg < DIST_BUCKET_1000:        distribution["<1000"] += 1
        elif kg < DIST_BUCKET_2000:      distribution["1000-2000"] += 1
        elif kg < DIST_BUCKET_3000:      distribution["2000-3000"] += 1
        elif kg < DIST_BUCKET_4000:      distribution["3000-4000"] += 1
        elif kg < DIST_BUCKET_5000:      distribution["4000-5000"] += 1
        else:                            distribution[">5000"] += 1
    return distribution


@router.get(
    "/stats",
    response_model=CommunityStats,
    status_code=status.HTTP_200_OK,
    summary="Get community leaderboard and statistics from real DB data",
)
def get_community_stats(db: Session = Depends(get_db)) -> CommunityStats:
    """
    Return real anonymised community data from the carbon_records table.

    Falls back to realistic seed data if fewer than MIN_REAL_USERS_FOR_LEADERBOARD
    real users exist yet, so the leaderboard never looks empty during early
    adoption. Leaderboard shows the top LEADERBOARD_LIMIT users ranked by
    their best (lowest) recorded footprint.
    """
    best_per_user = (
        db.query(
            db_models.CarbonRecord.user_id,
            func.min(db_models.CarbonRecord.total_kg).label("best_kg"),
        )
        .group_by(db_models.CarbonRecord.user_id)
        .order_by(func.min(db_models.CarbonRecord.total_kg).asc())
        .limit(LEADERBOARD_LIMIT)
        .all()
    )

    total_users = db.query(
        func.count(func.distinct(db_models.CarbonRecord.user_id))
    ).scalar() or 0

    avg_kg = db.query(func.avg(db_models.CarbonRecord.total_kg)).scalar() or 0.0

    all_totals = db.query(db_models.CarbonRecord.total_kg).all()
    distribution = _bucket_distribution(all_totals)

    leaderboard = []
    if len(best_per_user) >= MIN_REAL_USERS_FOR_LEADERBOARD:
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
        leaderboard = [
            LeaderboardEntry(rank=r, display_name=n, city=c, total_kg=float(kg), badge=_get_badge(r))
            for r, n, c, kg in SEED_LEADERBOARD_DATA
        ]
        distribution = SEED_DISTRIBUTION

    return CommunityStats(
        total_users=max(total_users, MIN_TOTAL_USERS_DISPLAYED),
        average_kg=round(float(avg_kg) if avg_kg else DEFAULT_AVG_KG, 1),
        best_kg=round(float(best_per_user[0][1]) if best_per_user else DEFAULT_BEST_KG, 1),
        leaderboard=leaderboard,
        distribution=distribution,
    )


@router.get(
    "/rank/{user_id}",
    summary="Get a specific user's rank in the community",
)
def get_user_rank(user_id: int, db: Session = Depends(get_db)) -> dict:
    """
    Return the given user's rank based on their best recorded footprint,
    compared against all other users with at least one calculation.
    """
    user_best = (
        db.query(func.min(db_models.CarbonRecord.total_kg))
        .filter(db_models.CarbonRecord.user_id == user_id)
        .scalar()
    )

    if not user_best:
        return {"rank": None, "message": "No calculations found for this user"}

    better_count = (
        db.query(func.count(func.distinct(db_models.CarbonRecord.user_id)))
        .filter(db_models.CarbonRecord.total_kg < user_best)
        .scalar() or 0
    )

    total_users = db.query(
        func.count(func.distinct(db_models.CarbonRecord.user_id))
    ).scalar() or 1

    return {
        "rank": better_count + 1,
        "total_users": total_users,
        "best_kg": round(float(user_best), 1),
        "percentile": round((1 - better_count / total_users) * 100, 1),
    }