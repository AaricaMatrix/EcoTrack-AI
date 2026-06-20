# backend/app/services/carbon_calculator.py
# Core carbon footprint calculation engine.
# All emission factors sourced from IPCC AR6, EPA 2023, UK Carbon Trust, CEA India 2023.
# Pure functions — no side effects, no I/O — safe to unit test in isolation.

from datetime import datetime, timezone
from app.models.schemas import CarbonInputFull, CategoryBreakdown, CarbonResult

# ── Time Conversion Constants ─────────────────────────────────────────────────
WEEKS_PER_YEAR = 52
MONTHS_PER_YEAR = 12
PERCENT_DIVISOR = 100

# ── Diet Calculation Constants ────────────────────────────────────────────────
OMNIVORE_BASELINE_MEAT_MEALS_PER_WEEK = 7
DEFAULT_WASTE_MULTIPLIER = 1.15

# ── Flight Distribution Assumption ────────────────────────────────────────────
# Average traveller assumed to split flights 50/50 short-haul vs long-haul
FLIGHT_SHORT_HAUL_RATIO = 0.5
FLIGHT_LONG_HAUL_RATIO = 0.5

# ── Comparison Benchmarks ─────────────────────────────────────────────────────
GLOBAL_AVG_KG = 4000.0    # IPCC global per-capita average
INDIA_AVG_KG = 1800.0     # India per-capita average (World Bank)

# ── Emission Factors ──────────────────────────────────────────────────────────
TRANSPORT_FACTORS: dict = {
    "car": {
        "petrol":   0.192,
        "diesel":   0.171,
        "hybrid":   0.110,
        "electric": 0.053,
        "none":     0.000,
    },
    "public_transit_per_km": 0.089,
    "flight_short_haul":     255.0,
    "flight_long_haul":      1050.0,
}

HOME_FACTORS: dict = {
    "electricity_india": 0.716,
    "gas_per_unit":      2.03,
}

DIET_FACTORS: dict = {
    "base": {
        "vegan":       1500.0,
        "vegetarian":  1700.0,
        "pescatarian": 2000.0,
        "omnivore":    2500.0,
    },
    "extra_meat_meal": 3.5,
    "waste_multiplier": {
        "low":    1.00,
        "medium": 1.15,
        "high":   1.30,
    },
}

SHOPPING_FACTORS: dict = {
    "clothing_item":    10.0,
    "electronics_item": 300.0,
    "online_order":     0.5,
}

# ── Rating Threshold Constants ────────────────────────────────────────────────
RATING_EXCELLENT_MAX = 1500
RATING_GOOD_MAX      = 2500
RATING_AVERAGE_MAX   = 4000
RATING_HIGH_MAX      = 7000

# ── Percentile Threshold Constants ────────────────────────────────────────────
PERCENTILE_BANDS = [
    (1000,  5.0),
    (2000,  20.0),
    (3000,  40.0),
    (4500,  60.0),
    (7000,  80.0),
    (10000, 90.0),
]
PERCENTILE_WORST = 97.0


def calculate_transport(transport) -> float:
    """
    Calculate annual transport kg CO2e.

    Converts weekly distances to annual, applies the emission factor for the
    car's fuel type, and adds flight emissions split evenly between
    short-haul and long-haul trips.
    """
    annual_car_km = transport.car_km_per_week * WEEKS_PER_YEAR
    car_factor = TRANSPORT_FACTORS["car"].get(transport.car_fuel_type, 0.192)
    car_emissions = annual_car_km * car_factor

    transit_emissions = (
        transport.public_transport_km_per_week * WEEKS_PER_YEAR
        * TRANSPORT_FACTORS["public_transit_per_km"]
    )

    flight_emissions = (
        transport.flights_per_year * FLIGHT_SHORT_HAUL_RATIO * TRANSPORT_FACTORS["flight_short_haul"]
        + transport.flights_per_year * FLIGHT_LONG_HAUL_RATIO * TRANSPORT_FACTORS["flight_long_haul"]
    )

    return round(car_emissions + transit_emissions + flight_emissions, 2)


def calculate_home(home) -> float:
    """
    Calculate annual per-capita home energy kg CO2e.

    Scales electricity emissions down by the household's renewable energy
    percentage, then divides the household total by occupant count to get
    a per-person figure.
    """
    annual_kwh = home.electricity_kwh_per_month * MONTHS_PER_YEAR

    effective_factor = HOME_FACTORS["electricity_india"] * (
        1 - home.renewable_energy_percent / PERCENT_DIVISOR
    )
    electricity_emissions = annual_kwh * effective_factor

    gas_emissions = home.gas_units_per_month * MONTHS_PER_YEAR * HOME_FACTORS["gas_per_unit"]

    return round(
        (electricity_emissions + gas_emissions) / max(home.num_people_in_home, 1), 2
    )


def calculate_diet(diet) -> float:
    """
    Calculate annual diet kg CO2e.

    Starts from a baseline figure for the user's diet type, adds extra
    emissions for meat meals consumed above the omnivore baseline, and
    applies a multiplier for the user's food waste level.
    """
    base = DIET_FACTORS["base"].get(diet.diet_type, DIET_FACTORS["base"]["omnivore"])

    excess_meat_meals = max(
        0.0, diet.meat_meals_per_week - OMNIVORE_BASELINE_MEAT_MEALS_PER_WEEK
    )
    meat_adjustment = excess_meat_meals * WEEKS_PER_YEAR * DIET_FACTORS["extra_meat_meal"]

    waste_mult = DIET_FACTORS["waste_multiplier"].get(
        diet.food_waste_level, DEFAULT_WASTE_MULTIPLIER
    )
    return round((base + meat_adjustment) * waste_mult, 2)


def calculate_shopping(shopping) -> float:
    """Calculate annual shopping and consumer goods kg CO2e."""
    clothing = shopping.new_clothes_per_year * SHOPPING_FACTORS["clothing_item"]
    electronics = shopping.electronics_per_year * SHOPPING_FACTORS["electronics_item"]
    delivery = (
        shopping.online_shopping_orders_per_month
        * MONTHS_PER_YEAR
        * SHOPPING_FACTORS["online_order"]
    )
    return round(clothing + electronics + delivery, 2)


def get_rating(total_kg: float) -> str:
    """
    Map total annual kg CO2e to a human-readable rating tier.

    Thresholds are based on the IPCC 1.5C compatible per-capita carbon
    budget, with intermediate bands derived from current global and
    India average emissions data.
    """
    if total_kg < RATING_EXCELLENT_MAX:  return "excellent"
    elif total_kg < RATING_GOOD_MAX:     return "good"
    elif total_kg < RATING_AVERAGE_MAX:  return "average"
    elif total_kg < RATING_HIGH_MAX:     return "high"
    else:                                return "critical"


def get_percentile(total_kg: float) -> float:
    """
    Approximate the user's global emissions percentile (0-100).

    A lower percentile is better — 5.0 means the user emits less than 95%
    of the comparison population. Bands are approximated from World Bank
    income-distribution and Our World in Data emissions data.
    """
    for threshold, percentile in PERCENTILE_BANDS:
        if total_kg < threshold:
            return percentile
    return PERCENTILE_WORST


def calculate_full_footprint(data: CarbonInputFull, user_id: int = None) -> CarbonResult:
    """
    Orchestrate all four category calculators into one CarbonResult.

    Each category is computed independently so the per-category breakdown
    remains visible to the caller, then summed for the annual total.
    """
    transport_kg = calculate_transport(data.transport)
    home_kg      = calculate_home(data.home_energy)
    diet_kg      = calculate_diet(data.diet)
    shopping_kg  = calculate_shopping(data.shopping)
    total_kg     = round(transport_kg + home_kg + diet_kg + shopping_kg, 2)

    breakdown = CategoryBreakdown(
        transport=transport_kg,
        home_energy=home_kg,
        diet=diet_kg,
        shopping=shopping_kg,
        total=total_kg,
    )

    return CarbonResult(
        user_id=user_id,
        footprint=breakdown,
        global_avg_kg=GLOBAL_AVG_KG,
        india_avg_kg=INDIA_AVG_KG,
        percentile=get_percentile(total_kg),
        rating=get_rating(total_kg),
        calculated_at=datetime.now(timezone.utc),
    )