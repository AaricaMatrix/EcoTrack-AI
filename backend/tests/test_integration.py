# backend/tests/test_integration.py
# Integration tests that hit the actual FastAPI endpoints via TestClient.
# These verify the full request/response cycle including validation, auth, and routing.
# Run with: pytest tests/test_integration.py -v --tb=short

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient     # HTTPX-based sync test client for FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

# ── In-memory SQLite for tests — isolated from dev database ──────────────────
TEST_DATABASE_URL = "sqlite:///./test_integration.db"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Replace the real DB session with the test DB session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override the DB dependency so tests use isolated test DB
app.dependency_overrides[get_db] = override_get_db

# Drop all tables first to ensure a clean state across test runs on Windows
Base.metadata.drop_all(bind=engine)
# Create all tables in test DB before running tests
Base.metadata.create_all(bind=engine)

# Single TestClient instance shared across all tests
client = TestClient(app, raise_server_exceptions=True)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def registered_token():
    """Register a test user and return their JWT token."""
    res = client.post("/api/auth/register", json={
        "name": "Test User",
        "email": "integration@test.com",
        "password": "testpassword123"
    })
    assert res.status_code == 201
    return res.json()["access_token"]


@pytest.fixture
def carbon_payload():
    """Valid carbon calculation payload."""
    return {
        "transport": {"car_km_per_week": 100, "car_fuel_type": "petrol", "flights_per_year": 2, "public_transport_km_per_week": 50},
        "home_energy": {"electricity_kwh_per_month": 200, "gas_units_per_month": 20, "num_people_in_home": 4, "renewable_energy_percent": 0},
        "diet": {"diet_type": "omnivore", "meat_meals_per_week": 7, "food_waste_level": "medium"},
        "shopping": {"new_clothes_per_year": 15, "electronics_per_year": 1, "online_shopping_orders_per_month": 8},
        "country": "IN"
    }


# ── Health Endpoint ───────────────────────────────────────────────────────────

class TestHealthEndpoints:

    def test_root_returns_running(self) -> None:
        """GET / must return running status."""
        res = client.get("/")
        assert res.status_code == 200
        assert res.json()["status"] == "running"

    def test_health_returns_healthy(self) -> None:
        """GET /health must return healthy status."""
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"


# ── Auth Endpoints ────────────────────────────────────────────────────────────

class TestAuthEndpoints:

    def test_register_new_user(self) -> None:
        """POST /api/auth/register must create user and return JWT."""
        res = client.post("/api/auth/register", json={
            "name": "New User",
            "email": "newuser@test.com",
            "password": "securepass123"
        })
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email_rejected(self) -> None:
        """Registering same email twice must return 400."""
        payload = {"name": "Dup User", "email": "dup@test.com", "password": "password123"}
        client.post("/api/auth/register", json=payload)   # First registration
        res = client.post("/api/auth/register", json=payload)  # Duplicate
        assert res.status_code == 400
        assert "already registered" in res.json()["detail"].lower()

    def test_register_weak_password_rejected(self) -> None:
        """Password under 8 chars must return 422."""
        res = client.post("/api/auth/register", json={
            "name": "Weak Pass", "email": "weak@test.com", "password": "short"
        })
        assert res.status_code == 422

    def test_login_valid_credentials(self, registered_token) -> None:
        """POST /api/auth/login with valid credentials must return JWT."""
        res = client.post("/api/auth/login", json={
            "email": "integration@test.com",
            "password": "testpassword123"
        })
        assert res.status_code == 200
        assert "access_token" in res.json()

    def test_login_wrong_password_returns_401(self) -> None:
        """Wrong password must return 401 — not 200 or 500."""
        res = client.post("/api/auth/login", json={
            "email": "integration@test.com",
            "password": "wrongpassword"
        })
        assert res.status_code == 401

    def test_get_me_with_valid_token(self, registered_token) -> None:
        """GET /api/auth/me with valid Bearer token must return user profile."""
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {registered_token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == "integration@test.com"
        assert "hashed_password" not in data   # Must never expose password hash

    def test_get_me_without_token_returns_401(self) -> None:
        """GET /api/auth/me without token must return 401."""
        res = client.get("/api/auth/me")
        assert res.status_code == 401


# ── Carbon Endpoints ──────────────────────────────────────────────────────────

class TestCarbonEndpoints:

    def test_anonymous_calculation_succeeds(self, carbon_payload) -> None:
        """POST /api/carbon/calculate/anonymous must return valid CarbonResult."""
        res = client.post("/api/carbon/calculate/anonymous", json=carbon_payload)
        assert res.status_code == 200
        data = res.json()
        assert "footprint" in data
        assert data["footprint"]["total"] > 0
        assert data["rating"] in ["excellent", "good", "average", "high", "critical"]
        assert data["global_avg_kg"] == 4000.0
        assert data["india_avg_kg"] == 1800.0

    def test_anonymous_total_equals_sum_of_parts(self, carbon_payload) -> None:
        """Total footprint must equal sum of all category footprints."""
        res = client.post("/api/carbon/calculate/anonymous", json=carbon_payload)
        fp = res.json()["footprint"]
        expected = round(fp["transport"] + fp["home_energy"] + fp["diet"] + fp["shopping"], 2)
        assert fp["total"] == expected

    def test_negative_car_km_rejected(self, carbon_payload) -> None:
        """Negative car_km_per_week must return 422 Unprocessable Entity."""
        carbon_payload["transport"]["car_km_per_week"] = -100
        res = client.post("/api/carbon/calculate/anonymous", json=carbon_payload)
        assert res.status_code == 422

    def test_invalid_fuel_type_rejected(self, carbon_payload) -> None:
        """Invalid fuel type must return 422."""
        carbon_payload["transport"]["car_fuel_type"] = "nuclear"
        res = client.post("/api/carbon/calculate/anonymous", json=carbon_payload)
        assert res.status_code == 422

    def test_authenticated_calculation_saves_to_db(self, registered_token, carbon_payload) -> None:
        """Authenticated calculation must save to DB and return result."""
        res = client.post(
            "/api/carbon/calculate",
            json=carbon_payload,
            headers={"Authorization": f"Bearer {registered_token}"}
        )
        assert res.status_code == 200
        assert res.json()["footprint"]["total"] > 0

    def test_history_returns_saved_records(self, registered_token, carbon_payload) -> None:
        """GET /api/carbon/history must return previously saved records."""
        res = client.get(
            "/api/carbon/history",
            headers={"Authorization": f"Bearer {registered_token}"}
        )
        assert res.status_code == 200
        assert isinstance(res.json(), list)
        assert len(res.json()) > 0


# ── Predictions Endpoint ──────────────────────────────────────────────────────

class TestPredictionsEndpoint:

    def test_forecast_returns_six_months(self) -> None:
        """POST /api/predictions/forecast must return exactly 6 months."""
        breakdown = {"transport": 2000.0, "home_energy": 600.0, "diet": 2500.0, "shopping": 400.0, "total": 5500.0}
        res = client.post("/api/predictions/forecast", json=breakdown)
        assert res.status_code == 200
        data = res.json()
        assert len(data["months"]) == 6
        assert len(data["predicted_kg"]) == 6
        assert data["trend"] in ["improving", "stable", "worsening"]

    def test_forecast_predictions_non_negative(self) -> None:
        """All predicted values must be >= 0."""
        breakdown = {"transport": 500.0, "home_energy": 200.0, "diet": 1500.0, "shopping": 100.0, "total": 2300.0}
        res = client.post("/api/predictions/forecast", json=breakdown)
        assert all(p >= 0 for p in res.json()["predicted_kg"])


# ── Tips Endpoint ─────────────────────────────────────────────────────────────

class TestTipsEndpoint:

    def test_tips_returns_list(self) -> None:
        """POST /api/tips/personalized must return a list of tips."""
        breakdown = {"transport": 3000.0, "home_energy": 1000.0, "diet": 2500.0, "shopping": 600.0, "total": 7100.0}
        res = client.post("/api/tips/personalized", json=breakdown)
        assert res.status_code == 200
        tips = res.json()
        assert isinstance(tips, list)
        assert len(tips) > 0

    def test_tips_have_required_fields(self) -> None:
        """Each tip must have title, description, impact_kg_per_year, difficulty."""
        breakdown = {"transport": 3000.0, "home_energy": 1000.0, "diet": 2500.0, "shopping": 600.0, "total": 7100.0}
        res = client.post("/api/tips/personalized", json=breakdown)
        for tip in res.json():
            assert "title" in tip
            assert "description" in tip
            assert "impact_kg_per_year" in tip
            assert tip["difficulty"] in ["easy", "medium", "hard"]


# ── Cleanup ───────────────────────────────────────────────────────────────────

def teardown_module(module):
    """Remove test database file after all tests complete."""
    import os
    engine.dispose()
    if os.path.exists("./test_integration.db"):
        try:
            os.remove("./test_integration.db")
        except Exception:
            pass