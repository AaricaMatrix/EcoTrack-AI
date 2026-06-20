# backend/app/services/anomaly_detector.py
# Real ML anomaly detection using scikit-learn's Isolation Forest.
# Detects statistically unusual emission spikes in a user's personal history.

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from app.models.schemas import AnomalyRequest, AnomalyResult

# ── Model Configuration Constants ─────────────────────────────────────────────
RANDOM_STATE = 42              # Fixed seed — identical trees every run
N_ESTIMATORS = 100             # Number of trees — stable on small datasets
CONTAMINATION = 0.15           # Expected fraction of outliers in personal history
Z_SCORE_FLAG_THRESHOLD = 2.0   # Flag a category if more than 2 std devs above mean

CATEGORIES = ["transport", "home_energy", "diet", "shopping"]


def _breakdown_to_array(bd) -> list[float]:
    """Convert a CategoryBreakdown object to a flat list in fixed category order."""
    return [bd.transport, bd.home_energy, bd.diet, bd.shopping]


def detect_anomaly(req: AnomalyRequest) -> AnomalyResult:
    """
    Run Isolation Forest on the user's historical emission records to
    determine whether the current reading is a statistical anomaly.

    Isolation Forest builds random decision trees that try to isolate each
    data point; anomalies are isolated faster (fewer splits) because they
    sit far from the cluster of normal data, giving them a low anomaly
    score. Training on the user's own history (rather than a global
    threshold) means someone who normally drives a lot isn't flagged just
    for having a high transport score, and multivariate anomalies across
    categories are caught, not just single-category spikes.
    """
    history_arrays = [_breakdown_to_array(h) for h in req.history]
    X_history = np.array(history_arrays, dtype=np.float64)
    X_current = np.array([_breakdown_to_array(req.current)], dtype=np.float64)

    # Normalise so high-magnitude categories (diet ~2500) don't dominate
    # low-magnitude ones (shopping ~400) in the anomaly score
    scaler = StandardScaler()
    X_history_scaled = scaler.fit_transform(X_history)
    X_current_scaled = scaler.transform(X_current)

    clf = IsolationForest(
        n_estimators=N_ESTIMATORS,
        contamination=CONTAMINATION,
        random_state=RANDOM_STATE,
        max_samples="auto",
    )
    clf.fit(X_history_scaled)

    prediction = clf.predict(X_current_scaled)[0]
    raw_score = float(clf.score_samples(X_current_scaled)[0])
    is_anomaly = prediction == -1   # Isolation Forest convention: -1 = outlier

    z_scores, flagged = _compute_z_scores(X_history, req.current)
    explanation = _build_explanation(is_anomaly, flagged, z_scores)

    return AnomalyResult(
        is_anomaly=is_anomaly,
        anomaly_score=raw_score,
        z_scores=z_scores,
        flagged_categories=flagged,
        explanation=explanation,
    )


def _compute_z_scores(X_history: np.ndarray, current) -> tuple[dict, list]:
    """
    Compute per-category z-scores against the user's own historical mean
    and standard deviation, and flag any category above the threshold.
    """
    history_mean = X_history.mean(axis=0)
    history_std = X_history.std(axis=0)
    current_vals = _breakdown_to_array(current)

    z_scores: dict[str, float] = {}
    flagged: list[str] = []

    for i, cat in enumerate(CATEGORIES):
        std = history_std[i] if history_std[i] > 0 else 1.0
        z = (current_vals[i] - history_mean[i]) / std
        z_scores[cat] = round(float(z), 2)
        if z > Z_SCORE_FLAG_THRESHOLD:
            flagged.append(cat)

    return z_scores, flagged


def _build_explanation(is_anomaly: bool, flagged: list, z_scores: dict) -> str:
    """Build a human-readable explanation string for the anomaly result."""
    if not is_anomaly:
        return "Your emission levels are consistent with your recent history."

    if flagged:
        cat_descriptions = {
            "transport": "transport (driving/flights)",
            "home_energy": "home energy usage",
            "diet": "diet choices",
            "shopping": "shopping activity",
        }
        flagged_readable = " and ".join(cat_descriptions.get(c, c) for c in flagged)
        z_max = max(z_scores[c] for c in flagged)
        return (
            f"Unusual spike detected in {flagged_readable}. "
            f"Your highest flagged category is {round(z_max, 1)}x your typical standard deviation above your personal average. "
            f"Check for one-off events like a long trip, unusually high electricity bill, or major purchase."
        )

    return (
        "Your overall emission pattern this period is unusual compared to your history, "
        "though no single category stands out dramatically. "
        "This may reflect a combination of small increases across multiple areas."
    )