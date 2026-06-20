# backend/app/services/ml_predictor.py
# Polynomial regression pipeline for 6-month carbon trend forecasting.
# Uses scikit-learn with fixed random_state — outputs are fully deterministic.
# Tips engine ranks recommendations by absolute CO2e impact, highest first.

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import Pipeline
from datetime import datetime, timedelta, timezone
from typing import List
from app.models.schemas import CategoryBreakdown, PredictionResult, Tip

# ── Model Constants ────────────────────────────────────────────────────────
RNG_SEED = 42                      # Fixed seed — every run is deterministic
FORECAST_MONTHS = 6                # Months to predict forward
HISTORY_MONTHS = 6                 # Months of history used to fit the model
RIDGE_ALPHA = 1.0                  # L2 regularisation strength

# ── Historical Simulation Constants ──────────────────────────────────────────
HISTORY_NOISE_RANGE = 0.06         # ±6% month-to-month random variation
HISTORY_TREND_RATE = 0.018         # ~1.8% higher per month further in the past

# ── Prediction Bounds ─────────────────────────────────────────────────────
MAX_PREDICTION_MULTIPLIER = 3.0    # Predictions clamped to [0, 3x current]
DAYS_PER_MONTH_APPROX = 30         # Used to step forward month labels

# ── Trend Classification Thresholds ──────────────────────────────────────────
TREND_IMPROVING_THRESHOLD_PCT = -5.0
TREND_WORSENING_THRESHOLD_PCT = 5.0

# ── Reduction Potential ────────────────────────────────────────────────────
REDUCTION_POTENTIAL_RATE = 0.30    # Assume 30% achievable reduction on the largest category

# ── Tip Trigger Thresholds (kg CO2e/year) and impact rates ──────────────────
TRANSPORT_EV_THRESHOLD = 2000
TRANSPORT_EV_IMPACT_RATE = 0.65
TRANSPORT_WFH_THRESHOLD = 500
TRANSPORT_WFH_IMPACT_RATE = 0.25
TRANSPORT_TRAIN_THRESHOLD = 300
TRANSPORT_TRAIN_FIXED_IMPACT = 230.0

HOME_SOLAR_THRESHOLD = 800
HOME_SOLAR_IMPACT_RATE = 0.60
HOME_APPLIANCE_THRESHOLD = 400
HOME_APPLIANCE_IMPACT_RATE = 0.30

DIET_MEATLESS_THRESHOLD = 2000
DIET_MEATLESS_FIXED_IMPACT = 180.0
DIET_WASTE_THRESHOLD = 2500
DIET_WASTE_IMPACT_RATE = 0.13

SHOPPING_SECONDHAND_THRESHOLD = 500
SHOPPING_SECONDHAND_IMPACT_RATE = 0.20

MAX_TIPS_RETURNED = 5


def _simulate_history(current_total: float, months_back: int = HISTORY_MONTHS) -> np.ndarray:
    """
    Generate synthetic historical footprint data when no real DB records exist.

    Uses a deterministic seed derived from the footprint value so the same
    input always produces the same simulated history. Models a realistic
    prior-improvement arc where older months trend slightly higher.
    """
    rng = np.random.default_rng(seed=(RNG_SEED + int(round(current_total / 10))))

    history = []
    for i in range(months_back, 0, -1):
        noise = rng.uniform(-HISTORY_NOISE_RANGE, HISTORY_NOISE_RANGE)
        trend = 1 + (i * HISTORY_TREND_RATE)
        history.append(current_total * trend * (1 + noise))

    return np.array(history, dtype=np.float64)


def predict_future_footprint(
    breakdown: CategoryBreakdown,
    months_ahead: int = FORECAST_MONTHS,
    historical_totals: list[float] = None,
) -> PredictionResult:
    """
    Fit a degree-2 polynomial Ridge regression on historical footprint data
    and predict forward.

    Why polynomial degree 2 instead of linear: linear regression assumes a
    constant rate of change forever, which is physically unrealistic.
    Degree 2 captures the common "easy wins first" pattern — rapid early
    reduction followed by a plateau. Ridge regularisation (vs plain OLS)
    prevents the model from overfitting on the small number of data points.
    """
    current_total = breakdown.total

    if historical_totals and len(historical_totals) >= 3:
        historical = np.array(historical_totals, dtype=np.float64)
    else:
        historical = _simulate_history(current_total)

    n = len(historical)
    X_train = np.arange(n).reshape(-1, 1)
    y_train = historical

    model = Pipeline([
        ("poly", PolynomialFeatures(degree=2, include_bias=False)),
        ("reg",  Ridge(alpha=RIDGE_ALPHA, random_state=RNG_SEED)),
    ])
    model.fit(X_train, y_train)

    X_future = np.arange(n, n + months_ahead).reshape(-1, 1)
    raw_predictions = model.predict(X_future)

    predicted = np.clip(
        raw_predictions, 0.0, current_total * MAX_PREDICTION_MULTIPLIER
    ).tolist()

    now = datetime.now(timezone.utc)
    month_labels = [
        (now + timedelta(days=DAYS_PER_MONTH_APPROX * i)).strftime("%b %Y")
        for i in range(1, months_ahead + 1)
    ]

    first, last = predicted[0], predicted[-1]
    change_pct = (last - first) / max(abs(first), 1.0) * 100

    if change_pct < TREND_IMPROVING_THRESHOLD_PCT:    trend = "improving"
    elif change_pct > TREND_WORSENING_THRESHOLD_PCT:  trend = "worsening"
    else:                                             trend = "stable"

    max_category = max(
        breakdown.transport, breakdown.home_energy, breakdown.diet, breakdown.shopping
    )
    reduction_potential = round(max_category * REDUCTION_POTENTIAL_RATE, 2)

    return PredictionResult(
        months=month_labels,
        predicted_kg=[round(p, 1) for p in predicted],
        trend=trend,
        reduction_potential_kg=reduction_potential,
    )


def generate_tips(breakdown: CategoryBreakdown) -> List[Tip]:
    """
    Generate personalised, impact-ranked reduction tips from the breakdown.

    Only adds a tip when the user's emissions in that category exceed a
    meaningful threshold. Returns the top MAX_TIPS_RETURNED tips by impact
    so the user is not overwhelmed with low-value suggestions.
    """
    tips: List[Tip] = []
    priority = 1

    if breakdown.transport > TRANSPORT_EV_THRESHOLD:
        tips.append(Tip(
            category="transport", priority=priority,
            title="Switch to an Electric Vehicle",
            description="Switching from a petrol car to an EV cuts transport emissions by ~70%. India's FAME-II subsidies reduce upfront cost.",
            impact_kg_per_year=round(breakdown.transport * TRANSPORT_EV_IMPACT_RATE),
            difficulty="hard",
        ))
        priority += 1

    if breakdown.transport > TRANSPORT_WFH_THRESHOLD:
        tips.append(Tip(
            category="transport", priority=priority,
            title="Work from home 2 days per week",
            description="A 40% commute reduction directly cuts car and transit emissions with zero capital expenditure.",
            impact_kg_per_year=round(breakdown.transport * TRANSPORT_WFH_IMPACT_RATE),
            difficulty="medium",
        ))
        priority += 1

    if breakdown.transport > TRANSPORT_TRAIN_THRESHOLD:
        tips.append(Tip(
            category="transport", priority=priority,
            title="Replace one flight with train travel",
            description="Rajdhani/Shatabdi trains emit 90% less CO2 per km than domestic flights. Delhi-Mumbai by train saves ~200 kg CO2.",
            impact_kg_per_year=TRANSPORT_TRAIN_FIXED_IMPACT,
            difficulty="easy",
        ))
        priority += 1

    if breakdown.home_energy > HOME_SOLAR_THRESHOLD:
        tips.append(Tip(
            category="home_energy", priority=priority,
            title="Install rooftop solar panels",
            description="A 2 kW system covers 60-80% of Indian household electricity. 5-7 year payback, then free power for 20+ years.",
            impact_kg_per_year=round(breakdown.home_energy * HOME_SOLAR_IMPACT_RATE),
            difficulty="hard",
        ))
        priority += 1

    if breakdown.home_energy > HOME_APPLIANCE_THRESHOLD:
        tips.append(Tip(
            category="home_energy", priority=priority,
            title="Upgrade to 5-star BEE-rated appliances",
            description="5-star AC, fridge, and washing machine cut home energy by 30-40% and reduce monthly electricity bills.",
            impact_kg_per_year=round(breakdown.home_energy * HOME_APPLIANCE_IMPACT_RATE),
            difficulty="medium",
        ))
        priority += 1

    if breakdown.diet > DIET_MEATLESS_THRESHOLD:
        tips.append(Tip(
            category="diet", priority=priority,
            title="Try Meatless Mondays",
            description="One meat-free day per week saves 150-200 kg CO2e annually. Lentils (dal) have 20x less carbon than beef per gram of protein.",
            impact_kg_per_year=DIET_MEATLESS_FIXED_IMPACT,
            difficulty="easy",
        ))
        priority += 1

    if breakdown.diet > DIET_WASTE_THRESHOLD:
        tips.append(Tip(
            category="diet", priority=priority,
            title="Reduce food waste to low",
            description="Planning meals, storing food correctly, and composting scraps eliminates the carbon embedded in wasted food production.",
            impact_kg_per_year=round(breakdown.diet * DIET_WASTE_IMPACT_RATE),
            difficulty="easy",
        ))
        priority += 1

    if breakdown.shopping > SHOPPING_SECONDHAND_THRESHOLD:
        tips.append(Tip(
            category="shopping", priority=priority,
            title="Buy second-hand clothing",
            description="Fast fashion is among the most polluting industries. 10 second-hand items saves ~100 kg CO2e and prevents textile waste.",
            impact_kg_per_year=round(breakdown.shopping * SHOPPING_SECONDHAND_IMPACT_RATE),
            difficulty="easy",
        ))
        priority += 1

    tips.sort(key=lambda t: t.impact_kg_per_year, reverse=True)
    return tips[:MAX_TIPS_RETURNED]