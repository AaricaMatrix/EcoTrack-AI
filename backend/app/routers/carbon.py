# backend/app/routers/carbon.py

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import db_models
from app.models.schemas import CarbonInputFull, CarbonResult
from app.services.carbon_calculator import calculate_full_footprint
from app.routers.auth import get_current_user

router = APIRouter()


@router.post("/calculate", response_model=CarbonResult, status_code=200)
def calculate_authenticated(
    body: CarbonInputFull,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
) -> CarbonResult:
    """
    Calculate the full carbon footprint for an authenticated user and save it to the database.
    """
    result = calculate_full_footprint(body, user_id=current_user.id)
    record = db_models.CarbonRecord(
        user_id=current_user.id,
        transport_kg=result.footprint.transport,
        home_energy_kg=result.footprint.home_energy,
        diet_kg=result.footprint.diet,
        shopping_kg=result.footprint.shopping,
        total_kg=result.footprint.total,
    )
    db.add(record)
    db.commit()
    return result


@router.post("/calculate/anonymous", response_model=CarbonResult, status_code=200)
def calculate_anonymous(body: CarbonInputFull) -> CarbonResult:
    """
    Calculate the full carbon footprint for an anonymous user. Does not save to the database.
    """
    return calculate_full_footprint(body, user_id=None)


@router.get("/history")
def get_history(
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
    # [SECURITY] Bounded limit parameter — prevents a caller from passing
    # limit=1_000_000 and triggering an unbounded full-table scan.
    # ge=1 rejects zero or negative limits; le=100 caps memory per request.
    limit: int = Query(default=12, ge=1, le=100),
) -> list[dict]:
    """
    Returns the authenticated user's most recent carbon records.

    [SECURITY] The query is always filtered by current_user.id (from the
    verified JWT), never by a user-supplied ID parameter. This eliminates
    any IDOR risk on this endpoint.
    """
    records = (
        db.query(db_models.CarbonRecord)
        .filter(db_models.CarbonRecord.user_id == current_user.id)
        .order_by(db_models.CarbonRecord.calculated_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "transport_kg": r.transport_kg,
            "home_energy_kg": r.home_energy_kg,
            "diet_kg": r.diet_kg,
            "shopping_kg": r.shopping_kg,
            "total_kg": r.total_kg,
            "calculated_at": r.calculated_at.isoformat(),
        }
        for r in records
    ]
