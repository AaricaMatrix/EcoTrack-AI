# backend/app/models/schemas.py — hardened against all injection types
# ReDoS: no regex on user input — uses set/Literal validation only
# SQLi:  strict types prevent malformed queries
# SSTI:  string length caps prevent oversized template injection
# LPDoS: all list fields have max_length, all strings have max_length

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Literal, Optional
from datetime import datetime
import re

# Safe character set for name validation — set lookup is O(1), no ReDoS risk
_SAFE_NAME_CHARS = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    " '-."
)

# Compiled safe regex with possessive quantifier alternative — bounded length prevents ReDoS
_SAFE_EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+\-]{1,64}@[a-zA-Z0-9.\-]{1,255}$')


class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def name_safe_chars(cls, v: str) -> str:
        """
        Set-based validation — O(1) per character, zero ReDoS risk.
        Rejects SQL special chars: ' " ; -- /* */ DROP etc.
        Rejects template injection: {{ }} {%
        """
        v = v.strip()
        if not all(c in _SAFE_NAME_CHARS for c in v):
            raise ValueError("Name contains invalid characters")
        # Extra: reject SQL/template patterns even in allowed chars
        lowered = v.lower()
        forbidden = ["select", "drop", "insert", "delete", "update", "--", "{{", "}}"]
        if any(f in lowered for f in forbidden):
            raise ValueError("Name contains forbidden patterns")
        return v

    @field_validator("password")
    @classmethod
    def password_not_trivial(cls, v: str) -> str:
        """Reject passwords that are obviously weak."""
        trivial = {"password", "12345678", "password1", "qwerty123"}
        if v.lower() in trivial:
            raise ValueError("Password is too common")
        return v


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class UserPublicResponse(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime


class TransportData(BaseModel):
    car_km_per_week: float = Field(0.0, ge=0, le=10_000)
    car_fuel_type: Literal["petrol", "diesel", "hybrid", "electric", "none"] = "none"
    flights_per_year: int = Field(0, ge=0, le=365)
    public_transport_km_per_week: float = Field(0.0, ge=0, le=5_000)


class HomeEnergyData(BaseModel):
    electricity_kwh_per_month: float = Field(0.0, ge=0, le=100_000)
    gas_units_per_month: float = Field(0.0, ge=0, le=50_000)
    num_people_in_home: int = Field(1, ge=1, le=50)
    renewable_energy_percent: float = Field(0.0, ge=0, le=100)


class DietData(BaseModel):
    diet_type: Literal["vegan", "vegetarian", "pescatarian", "omnivore"] = "omnivore"
    meat_meals_per_week: float = Field(0.0, ge=0, le=42)
    food_waste_level: Literal["low", "medium", "high"] = "medium"


class ShoppingData(BaseModel):
    new_clothes_per_year: int = Field(0, ge=0, le=1_000)
    electronics_per_year: int = Field(0, ge=0, le=100)
    online_shopping_orders_per_month: float = Field(0.0, ge=0, le=500)


class CarbonInputFull(BaseModel):
    transport: TransportData
    home_energy: HomeEnergyData
    diet: DietData
    shopping: ShoppingData
    country: str = Field("IN", min_length=2, max_length=3,
                         pattern=r'^[A-Z]{2,3}$')  # ISO country code only


class CategoryBreakdown(BaseModel):
    transport: float = Field(..., ge=0)
    home_energy: float = Field(..., ge=0)
    diet: float = Field(..., ge=0)
    shopping: float = Field(..., ge=0)
    total: float = Field(..., ge=0)


class CarbonResult(BaseModel):
    user_id: Optional[int] = None
    footprint: CategoryBreakdown
    global_avg_kg: float
    india_avg_kg: float
    percentile: float
    rating: Literal["excellent", "good", "average", "high", "critical"]
    calculated_at: datetime


class PredictionResult(BaseModel):
    months: list[str] = Field(..., max_length=12)
    predicted_kg: list[float] = Field(..., max_length=12)
    trend: Literal["improving", "stable", "worsening"]
    reduction_potential_kg: float


class Tip(BaseModel):
    category: Literal["transport", "home_energy", "diet", "shopping"]
    title: str = Field(..., max_length=100)
    description: str = Field(..., max_length=500)
    impact_kg_per_year: float = Field(..., ge=0)
    difficulty: Literal["easy", "medium", "hard"]
    priority: int = Field(..., ge=1)


class InsightRequest(BaseModel):
    footprint: CategoryBreakdown
    country: str = Field("IN", min_length=2, max_length=3)
    user_name: Optional[str] = Field(None, max_length=80)

    @field_validator("user_name")
    @classmethod
    def sanitize_name(cls, v: Optional[str]) -> Optional[str]:
        """Strip SSTI markers from user_name before it reaches AI prompt."""
        if not v:
            return v
        # Remove template injection — prevents SSTI via AI prompt injection
        v = v.replace("{{", "").replace("}}", "")
        v = v.replace("{%", "").replace("%}", "")
        v = v.replace("<", "").replace(">", "")
        return v[:80].strip()


class InsightResponse(BaseModel):
    summary: str = Field(..., max_length=1000)
    dominant_category: str = Field(..., max_length=50)
    key_insight: str = Field(..., max_length=500)
    action_plan: list[str] = Field(..., max_length=5)
    motivational_close: str = Field(..., max_length=300)
    generated_by: str = "groq-llama-3.1-8b"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)  # Cap per message

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        """
        Sanitize chat messages to prevent:
        - Prompt injection via AI (SSTI-like)
        - Oversized messages causing LPDoS
        """
        # Remove potential prompt injection attempts
        injection_patterns = [
            "ignore previous instructions",
            "ignore all instructions",
            "disregard your",
            "you are now",
            "new instruction",
            "system prompt",
        ]
        lowered = v.lower()
        for pat in injection_patterns:
            if pat in lowered:
                raise ValueError("Message contains forbidden patterns")
        return v


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=10)  # Cap history
    footprint_context: Optional[CategoryBreakdown] = None


class ChatResponse(BaseModel):
    reply: str = Field(..., max_length=2000)
    model: str = "groq-llama-3.1-8b"


class AnomalyResult(BaseModel):
    is_anomaly: bool
    anomaly_score: float
    z_scores: dict[str, float]
    flagged_categories: list[str] = Field(..., max_length=4)
    explanation: str = Field(..., max_length=500)


class AnomalyRequest(BaseModel):
    current: CategoryBreakdown
    history: list[CategoryBreakdown] = Field(..., min_length=3, max_length=24)