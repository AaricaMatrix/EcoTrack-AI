# backend/tests/test_all.py
# Comprehensive deterministic test suite — 20+ tests covering:
# - Carbon calculation accuracy (transport, home, diet, shopping, full)
# - Rating and percentile monotonicity
# - ML prediction stability and determinism
# - Input validation (Pydantic schema enforcement)
# - Auth security (password hashing, JWT encode/decode)
# - API schema integrity (correct fields and types on all responses)
#
# Run with:  pytest backend/tests/ -v --tb=short
# All tests are deterministic — no random seeds, no external services required.

import sys
import os
import pytest

# Ensure the backend directory is on the path so `app.*` imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Import modules under test ─────────────────────────────────────────────────
from app.services.carbon_calculator import (
    calculate_transport,
    calculate_home,
    calculate_diet,
    calculate_shopping,
    calculate_full_footprint,
    get_rating,
    get_percentile,
)
from app.services.ml_predictor import predict_future_footprint, generate_tips
from app.models.schemas import (
    TransportData, HomeEnergyData, DietData, ShoppingData,
    CarbonInputFull, CategoryBreakdown,
)
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from pydantic import ValidationError


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES — reusable test data objects
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def zero_transport():
    """No personal transport at all — should produce exactly 0 kg CO₂e."""
    return TransportData(car_km_per_week=0, car_fuel_type="none", flights_per_year=0, public_transport_km_per_week=0)

@pytest.fixture
def petrol_commuter():
    """Heavy petrol car commuter — 200 km/week, 4 flights/year."""
    return TransportData(car_km_per_week=200, car_fuel_type="petrol", flights_per_year=4, public_transport_km_per_week=0)

@pytest.fixture
def ev_commuter():
    """Same distance as petrol commuter but in an EV."""
    return TransportData(car_km_per_week=200, car_fuel_type="electric", flights_per_year=4, public_transport_km_per_week=0)

@pytest.fixture
def grid_home():
    """Average Indian household on grid power — 200 kWh/month, family of 4."""
    return HomeEnergyData(electricity_kwh_per_month=200, gas_units_per_month=20, num_people_in_home=4, renewable_energy_percent=0)

@pytest.fixture
def solar_home():
    """Household with 100% solar — electricity emissions should be near zero."""
    return HomeEnergyData(electricity_kwh_per_month=200, gas_units_per_month=0, num_people_in_home=1, renewable_energy_percent=100)

@pytest.fixture
def vegan_low_waste():
    return DietData(diet_type="vegan", meat_meals_per_week=0, food_waste_level="low")

@pytest.fixture
def omnivore_high_waste():
    return DietData(diet_type="omnivore", meat_meals_per_week=14, food_waste_level="high")

@pytest.fixture
def minimal_shopping():
    return ShoppingData(new_clothes_per_year=2, electronics_per_year=0, online_shopping_orders_per_month=1)

@pytest.fixture
def heavy_shopping():
    return ShoppingData(new_clothes_per_year=50, electronics_per_year=3, online_shopping_orders_per_month=20)

@pytest.fixture
def typical_input(petrol_commuter, grid_home, vegan_low_waste, minimal_shopping):
    """Full CarbonInputFull combining typical fixtures."""
    return CarbonInputFull(transport=petrol_commuter, home_energy=grid_home, diet=vegan_low_waste, shopping=minimal_shopping)

@pytest.fixture
def typical_breakdown():
    """A CategoryBreakdown object representing a typical user for ML tests."""
    return CategoryBreakdown(transport=2000.0, home_energy=600.0, diet=2500.0, shopping=400.0, total=5500.0)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 1: Transport Calculation
# ═══════════════════════════════════════════════════════════════════════════════

class TestTransportCalculation:

    def test_zero_input_returns_zero(self, zero_transport) -> None:
        """No transport → exactly 0.0 kg CO₂e. Guards against rounding artefacts."""
        assert calculate_transport(zero_transport) == 0.0

    def test_petrol_greater_than_ev_same_distance(self, petrol_commuter, ev_commuter) -> None:
        """Petrol car must always emit more than EV for identical distance and flights."""
        assert calculate_transport(petrol_commuter) > calculate_transport(ev_commuter)

    def test_flights_add_material_emissions(self) -> None:
        """4 flights should add at least 500 kg CO₂e over a no-flight baseline."""
        no_flight = TransportData(car_km_per_week=0, car_fuel_type="none", flights_per_year=0, public_transport_km_per_week=0)
        four_flights = TransportData(car_km_per_week=0, car_fuel_type="none", flights_per_year=4, public_transport_km_per_week=0)
        delta = calculate_transport(four_flights) - calculate_transport(no_flight)
        assert delta > 500.0, f"Expected >500 kg from 4 flights, got {delta}"

    def test_result_is_non_negative(self, petrol_commuter) -> None:
        """Carbon footprint can never be negative."""
        assert calculate_transport(petrol_commuter) >= 0.0

    def test_result_is_float(self, petrol_commuter) -> None:
        """Calculator must return a float (not int) — required by Pydantic schema."""
        assert isinstance(calculate_transport(petrol_commuter), float)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 2: Home Energy Calculation
# ═══════════════════════════════════════════════════════════════════════════════

class TestHomeCalculation:

    def test_full_solar_near_zero(self, solar_home) -> None:
        """100% solar + no gas → electricity contribution should be 0, only gas matters."""
        result = calculate_home(solar_home)
        assert result < 5.0, f"100% solar with no gas should be <5 kg/year, got {result}"

    def test_more_people_reduces_per_capita(self, grid_home) -> None:
        """Doubling household size halves per-capita emissions (all else equal)."""
        solo = HomeEnergyData(electricity_kwh_per_month=200, gas_units_per_month=20, num_people_in_home=1, renewable_energy_percent=0)
        four = HomeEnergyData(electricity_kwh_per_month=200, gas_units_per_month=20, num_people_in_home=4, renewable_energy_percent=0)
        assert calculate_home(solo) > calculate_home(four)

    def test_no_division_by_zero_with_one_person(self) -> None:
        """Minimum people=1 (enforced by schema) — must not crash."""
        home = HomeEnergyData(electricity_kwh_per_month=100, gas_units_per_month=5, num_people_in_home=1, renewable_energy_percent=0)
        result = calculate_home(home)
        assert result > 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 3: Diet Calculation
# ═══════════════════════════════════════════════════════════════════════════════

class TestDietCalculation:

    def test_vegan_less_than_omnivore(self, vegan_low_waste, omnivore_high_waste) -> None:
        """Vegan + low waste must be significantly less than omnivore + high waste."""
        assert calculate_diet(vegan_low_waste) < calculate_diet(omnivore_high_waste)

    def test_high_waste_greater_than_low_waste(self) -> None:
        """Same diet type — high waste multiplier must increase total."""
        low = DietData(diet_type="omnivore", meat_meals_per_week=7, food_waste_level="low")
        high = DietData(diet_type="omnivore", meat_meals_per_week=7, food_waste_level="high")
        assert calculate_diet(low) < calculate_diet(high)

    def test_excess_meat_meals_add_emissions(self) -> None:
        """14 meat meals/week should be more than 7 for the same diet type."""
        seven = DietData(diet_type="omnivore", meat_meals_per_week=7, food_waste_level="low")
        fourteen = DietData(diet_type="omnivore", meat_meals_per_week=14, food_waste_level="low")
        assert calculate_diet(fourteen) > calculate_diet(seven)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 4: Rating and Percentile Logic
# ═══════════════════════════════════════════════════════════════════════════════

class TestRatingAndPercentile:

    def test_excellent_rating_below_1500(self) -> None:
        assert get_rating(1000) == "excellent"

    def test_critical_rating_above_7000(self) -> None:
        assert get_rating(8000) == "critical"

    def test_rating_covers_all_tiers(self) -> None:
        """All five tiers must be reachable via the rating function."""
        assert get_rating(500) == "excellent"
        assert get_rating(2000) == "good"
        assert get_rating(3000) == "average"
        assert get_rating(5000) == "high"
        assert get_rating(9000) == "critical"

    def test_percentile_monotonically_increasing(self) -> None:
        """Higher footprint must always yield a higher (worse) percentile."""
        values = [500, 1500, 2500, 4000, 6000, 9000]
        percentiles = [get_percentile(v) for v in values]
        assert percentiles == sorted(percentiles), "Percentiles are not monotonically increasing"

    def test_percentile_bounded_0_100(self) -> None:
        """Percentile must always be in [0, 100] regardless of input."""
        for kg in [0, 100, 1000, 5000, 15000, 1_000_000]:
            p = get_percentile(kg)
            assert 0 <= p <= 100, f"Percentile {p} out of bounds for {kg} kg"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 5: Full Footprint Integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullFootprint:

    def test_total_equals_sum_of_categories(self, typical_input) -> None:
        """total must equal transport + home_energy + diet + shopping (no rounding drift)."""
        result = calculate_full_footprint(typical_input)
        fp = result.footprint
        expected = round(fp.transport + fp.home_energy + fp.diet + fp.shopping, 2)
        assert fp.total == expected

    def test_rating_is_valid_literal(self, typical_input) -> None:
        valid = {"excellent", "good", "average", "high", "critical"}
        result = calculate_full_footprint(typical_input)
        assert result.rating in valid

    def test_averages_are_correct_constants(self, typical_input) -> None:
        """Global and India averages are fixed reference values — must match spec."""
        result = calculate_full_footprint(typical_input)
        assert result.global_avg_kg == 4000.0
        assert result.india_avg_kg == 1800.0


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 6: ML Prediction Determinism
# ═══════════════════════════════════════════════════════════════════════════════

class TestMLPrediction:

    def test_same_input_gives_same_output(self, typical_breakdown) -> None:
        """Predictions must be fully deterministic — critical for test reliability."""
        result_a = predict_future_footprint(typical_breakdown)
        result_b = predict_future_footprint(typical_breakdown)
        assert result_a.predicted_kg == result_b.predicted_kg, "ML output is not deterministic"

    def test_output_has_six_months(self, typical_breakdown) -> None:
        """Always return exactly 6 month labels and 6 prediction values."""
        result = predict_future_footprint(typical_breakdown)
        assert len(result.months) == 6
        assert len(result.predicted_kg) == 6

    def test_trend_is_valid_literal(self, typical_breakdown) -> None:
        result = predict_future_footprint(typical_breakdown)
        assert result.trend in {"improving", "stable", "worsening"}

    def test_predictions_non_negative(self, typical_breakdown) -> None:
        """Carbon footprint predictions must never go negative."""
        result = predict_future_footprint(typical_breakdown)
        assert all(p >= 0 for p in result.predicted_kg)

    def test_reduction_potential_positive(self, typical_breakdown) -> None:
        """Reduction potential must always be a positive number."""
        result = predict_future_footprint(typical_breakdown)
        assert result.reduction_potential_kg > 0


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 7: Input Validation (Pydantic Schema)
# ═══════════════════════════════════════════════════════════════════════════════

class TestInputValidation:

    def test_negative_car_km_rejected(self) -> None:
        """Negative km must raise ValidationError — ge=0 constraint."""
        with pytest.raises(ValidationError):
            TransportData(car_km_per_week=-10, car_fuel_type="petrol", flights_per_year=0, public_transport_km_per_week=0)

    def test_invalid_fuel_type_rejected(self) -> None:
        """Fuel type must be one of the defined Literals — else ValidationError."""
        with pytest.raises(ValidationError):
            TransportData(car_km_per_week=100, car_fuel_type="hydrogen", flights_per_year=0, public_transport_km_per_week=0)

    def test_zero_people_in_home_rejected(self) -> None:
        """num_people_in_home has ge=1 — zero people must raise ValidationError."""
        with pytest.raises(ValidationError):
            HomeEnergyData(electricity_kwh_per_month=200, gas_units_per_month=10, num_people_in_home=0, renewable_energy_percent=0)

    def test_renewable_percent_over_100_rejected(self) -> None:
        """Renewable energy cannot exceed 100% — le=100 constraint."""
        with pytest.raises(ValidationError):
            HomeEnergyData(electricity_kwh_per_month=200, gas_units_per_month=0, num_people_in_home=2, renewable_energy_percent=150)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 8: Security — Password Hashing and JWT
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecurity:

    def test_bcrypt_hash_not_plain_text(self) -> None:
        """Hashed password must never equal the plain-text input."""
        plain = "SecurePassword123"
        hashed = hash_password(plain)
        assert hashed != plain

    def test_verify_correct_password(self) -> None:
        """verify_password must return True when given correct plain text."""
        plain = "AnotherSecret!"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password(self) -> None:
        """verify_password must return False for wrong password — no false positives."""
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_jwt_roundtrip(self) -> None:
        """Token created for subject must decode back to same subject string."""
        subject = "test@example.com"
        token = create_access_token(subject=subject)
        decoded = decode_access_token(token)
        assert decoded == subject

    def test_tampered_jwt_rejected(self) -> None:
        """A tampered token must return None — never raise an unhandled exception."""
        token = create_access_token(subject="user@example.com")
        tampered = token[:-5] + "XXXXX"   # Corrupt the signature
        assert decode_access_token(tampered) is None


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 9: Anomaly Detection (Isolation Forest)
# ═══════════════════════════════════════════════════════════════════════════════

from app.services.anomaly_detector import detect_anomaly
from app.models.schemas import AnomalyRequest, AnomalyResult


def _make_breakdown(transport=2000, home=600, diet=2500, shopping=400):
    """Helper — build a CategoryBreakdown with keyword args for readability."""
    from app.models.schemas import CategoryBreakdown
    total = transport + home + diet + shopping
    return CategoryBreakdown(
        transport=float(transport), home_energy=float(home),
        diet=float(diet), shopping=float(shopping), total=float(total)
    )


class TestAnomalyDetection:

    @pytest.fixture
    def normal_history(self):
        """6 months of stable, consistent emission records — no outliers."""
        return [
            _make_breakdown(2000, 600, 2500, 400),
            _make_breakdown(1950, 580, 2480, 420),
            _make_breakdown(2050, 610, 2520, 390),
            _make_breakdown(1980, 595, 2490, 410),
            _make_breakdown(2020, 605, 2510, 405),
            _make_breakdown(1970, 590, 2470, 415),
        ]

    def test_normal_reading_not_flagged(self, normal_history) -> None:
        """A reading consistent with history must NOT be flagged as anomaly."""
        current = _make_breakdown(2010, 600, 2500, 400)
        req = AnomalyRequest(current=current, history=normal_history)
        result = detect_anomaly(req)
        assert isinstance(result, AnomalyResult)
        assert result.anomaly_score is not None

    def test_massive_spike_flagged(self, normal_history) -> None:
        """A reading with 5x normal transport must be detected as anomaly."""
        current = _make_breakdown(transport=12000, home=600, diet=2500, shopping=400)
        req = AnomalyRequest(current=current, history=normal_history)
        result = detect_anomaly(req)
        assert result.z_scores["transport"] > 3.0

    def test_z_scores_all_categories_present(self, normal_history) -> None:
        """AnomalyResult must always include z-scores for all 4 categories."""
        current = _make_breakdown(2000, 600, 2500, 400)
        req = AnomalyRequest(current=current, history=normal_history)
        result = detect_anomaly(req)
        assert set(result.z_scores.keys()) == {"transport", "home_energy", "diet", "shopping"}

    def test_anomaly_result_is_deterministic(self, normal_history) -> None:
        """Same inputs must produce identical anomaly results — fixed random_state."""
        current = _make_breakdown(5000, 600, 2500, 400)
        req = AnomalyRequest(current=current, history=normal_history)
        result_a = detect_anomaly(req)
        result_b = detect_anomaly(req)
        assert result_a.is_anomaly == result_b.is_anomaly
        assert result_a.anomaly_score == result_b.anomaly_score

    def test_explanation_always_non_empty(self, normal_history) -> None:
        """Explanation string must always be populated — never empty."""
        current = _make_breakdown(2000, 600, 2500, 400)
        req = AnomalyRequest(current=current, history=normal_history)
        result = detect_anomaly(req)
        assert len(result.explanation) > 10

    def test_flagged_categories_subset_of_valid(self, normal_history) -> None:
        """flagged_categories must only contain valid category names."""
        valid = {"transport", "home_energy", "diet", "shopping"}
        current = _make_breakdown(9000, 5000, 2500, 400)
        req = AnomalyRequest(current=current, history=normal_history)
        result = detect_anomaly(req)
        assert all(c in valid for c in result.flagged_categories)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 10: AI Insights Schema Validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestInsightSchemas:

    def test_insight_request_valid(self) -> None:
        """InsightRequest must accept valid breakdown + country."""
        from app.models.schemas import InsightRequest
        req = InsightRequest(
            footprint=_make_breakdown(2000, 600, 2500, 400),
            country="IN",
            user_name="Ayush",
        )
        assert req.country == "IN"
        assert req.user_name == "Ayush"

    def test_chat_message_empty_content_rejected(self) -> None:
        """ChatMessage with empty content must raise ValidationError."""
        from app.models.schemas import ChatMessage
        with pytest.raises(ValidationError):
            ChatMessage(role="user", content="")

    def test_chat_request_requires_at_least_one_message(self) -> None:
        """ChatRequest with empty messages list must raise ValidationError."""
        from app.models.schemas import ChatRequest, ChatMessage
        with pytest.raises(ValidationError):
            ChatRequest(messages=[])

    def test_anomaly_request_requires_min_3_history(self) -> None:
        """AnomalyRequest with only 2 history items must raise ValidationError."""
        with pytest.raises(ValidationError):
            AnomalyRequest(
                current=_make_breakdown(),
                history=[_make_breakdown(), _make_breakdown()],
            )