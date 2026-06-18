from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Literal, Optional
from datetime import datetime

class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def name_no_special_chars(cls, v: str) -> str:
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ '-.")
        if not all(c in allowed for c in v):
            raise ValueError("Name contains invalid characters")
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
    country: str = Field("IN", min_length=2, max_length=3)

# [SECURITY] CategoryBreakdown now enforces bounds on every field.
# Previously these were raw floats with no constraints, allowing callers to
# submit negative values, NaN, or astronomically large numbers (e.g. 1e308)
# that could cause numpy/sklearn errors or skew ML predictions silently.
#
# Upper bound (100_000 kg/year) ≈ 10× the heaviest realistic annual footprint.
# Lower bound (0.0) prevents negative emissions from distorting the model.
class CategoryBreakdown(BaseModel):
    transport: float = Field(0.0, ge=0.0, le=100_000.0)
    home_energy: float = Field(0.0, ge=0.0, le=100_000.0)
    diet: float = Field(0.0, ge=0.0, le=100_000.0)
    shopping: float = Field(0.0, ge=0.0, le=100_000.0)
    total: float = Field(0.0, ge=0.0, le=400_000.0)   # sum of all four categories

class CarbonResult(BaseModel):
    user_id: Optional[int] = None
    footprint: CategoryBreakdown
    global_avg_kg: float
    india_avg_kg: float
    percentile: float
    rating: Literal["excellent", "good", "average", "high", "critical"]
    calculated_at: datetime

class PredictionResult(BaseModel):
    months: list[str]
    predicted_kg: list[float]
    trend: Literal["improving", "stable", "worsening"]
    reduction_potential_kg: float

class Tip(BaseModel):
    category: Literal["transport", "home_energy", "diet", "shopping"]
    title: str
    description: str
    impact_kg_per_year: float
    difficulty: Literal["easy", "medium", "hard"]
    priority: int

class InsightRequest(BaseModel):
    footprint: CategoryBreakdown
    country: str = Field("IN", min_length=2, max_length=3)
    user_name: Optional[str] = Field(None, max_length=80)

class InsightResponse(BaseModel):
    summary: str
    dominant_category: str
    key_insight: str
    action_plan: list[str]
    motivational_close: str
    generated_by: str = "llama-3.1-8b-instant"

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)

class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=20)
    footprint_context: Optional[CategoryBreakdown] = None

class ChatResponse(BaseModel):
    reply: str
    model: str = "llama-3.1-8b-instant"

class AnomalyResult(BaseModel):
    is_anomaly: bool
    anomaly_score: float
    z_scores: dict[str, float]
    flagged_categories: list[str]
    explanation: str

class AnomalyRequest(BaseModel):
    current: CategoryBreakdown
    history: list[CategoryBreakdown] = Field(..., min_length=3, max_length=24)
