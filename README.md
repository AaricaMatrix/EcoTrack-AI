---
title: EcoTrack AI
emoji: 🌿
colorFrom: green
colorTo: green
sdk: docker
pinned: false
---

# 🌿 EcoTrack AI : Carbon Intelligence Platform

> AI-powered carbon footprint calculator with ML predictions, Groq AI insights, anomaly detection, AR product scanner, carbon offset marketplace, and community leaderboard.
> **Hack2Skill Challenge 3** submission.

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![CI Tests](https://github.com/Aaricacoding/EcoTrack-AI/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/Aaricacoding/EcoTrack-AI/actions/workflows/test.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.5-orange)](https://scikit-learn.org)
[![Tests](https://img.shields.io/badge/tests-62%20passing-brightgreen)](#testing)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**🔗 Live Demo**: https://eco-track-ai-three.vercel.app  
**⚙️ Backend API**: https://aaricacoding-ecotrack-ai.hf.space

---

## Challenge Requirements Coverage

✅ **Carbon Footprint Calculation:** Transport, Home Energy, Diet, and Shopping modules.
✅ **Carbon Reduction Recommendations:** Ranked tips sorted by CO₂ impact.
✅ **Machine Learning Forecasting:** 6-month predictive trends using Ridge Regression.
✅ **AI-Powered Insights:** Groq LLaMA footprint analysis and EcoBot coach.
✅ **Community Features:** Global anonymous ranking and footprint distribution.
✅ **Sustainability Awareness:** AR product scanner and offset marketplace.
✅ **Secure Authentication:** Robust JWT lifecycle and password hashing.
✅ **Accessibility Support:** Semantic HTML5 and ARIA compliant UI.
✅ **Responsive Design:** Mobile-first dashboard and metrics tracking.

---

## What It Does

| Feature                   | Detail                                                            |
| ------------------------- | ----------------------------------------------------------------- |
| **4-Step Carbon Wizard**  | Transport · Home Energy · Diet · Shopping — under 2 minutes       |
| **ML Trend Forecast**     | Polynomial Ridge Regression — 6-month carbon trajectory           |
| **Anomaly Detection**     | Isolation Forest detects unusual emission spikes in history       |
| **AI Insights**           | Groq LLaMA generates personalised narrative footprint analysis    |
| **EcoBot AI Coach**       | Multi-turn AI carbon coach — knows your exact footprint data      |
| **AR Carbon Scanner**     | Point camera at product barcode — instant CO₂ footprint overlay   |
| **Offset Marketplace**    | 4 verified Indian carbon offset projects with real pricing        |
| **Community Leaderboard** | Anonymous global ranking with footprint distribution chart        |
| **Smart Dashboard**       | Donut chart · comparison bars vs global/India benchmarks          |
| **Ranked Tips**           | Personalised actions sorted by CO₂ impact — highest savings first |
| **Secure Accounts**       | JWT + bcrypt authentication with IP rate limiting                 |

---

## Architecture

```
ecotrack-ai/
├── backend/
│   ├── app/
│   │   ├── core/        # config · security · database
│   │   ├── models/      # Pydantic schemas · SQLAlchemy ORM
│   │   ├── routers/     # auth · carbon · predictions · tips · insights
│   │   ├── services/    # carbon_calculator · ml_predictor · ai_insights · anomaly_detector
│   │   └── main.py      # FastAPI app · middleware · security headers
│   ├── tests/
│   │   ├── test_all.py          # Unit tests
│   │   └── test_integration.py  # Integration & API tests
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── index.html       # Single-file SPA · 9 tabs · Chart.js · ARIA compliant
```

---

## Quick Start

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

```bash
pytest backend/tests/ -v --tb=short
```

---

## API Endpoints

| Method | Endpoint                          | Description                         |
| ------ | --------------------------------- | ----------------------------------- |
| POST   | `/api/auth/register`              | Register new user                   |
| POST   | `/api/auth/login`                 | Login and receive JWT               |
| GET    | `/api/auth/me`                    | Get current user profile            |
| POST   | `/api/carbon/calculate`           | Calculate footprint (authenticated) |
| POST   | `/api/carbon/calculate/anonymous` | Calculate footprint (no auth)       |
| GET    | `/api/carbon/history`             | Get user calculation history        |
| POST   | `/api/predictions/forecast`       | 6-month ML forecast                 |
| POST   | `/api/tips/personalized`          | Get ranked reduction tips           |
| POST   | `/api/insights/analyze`           | Groq LLaMA footprint analysis       |
| POST   | `/api/insights/anomaly`           | Isolation Forest anomaly detection  |
| POST   | `/api/insights/chat`              | EcoBot multi-turn conversation      |
| GET    | `/api/community/stats`            | Global footprint distribution       |
| GET    | `/api/community/rank/{user_id}`   | Get user community rank             |
| GET    | `/health`                         | Health check                        |
| GET    | `/`                               | Root endpoint                       |

---

## Security

Robust security controls implemented across the API surface:

* **JWT Authentication:** Strict token lifecycle management.
* **Authorization Checks:** Ownership validation on private resources (e.g., IDOR prevention).
* **bcrypt Password Hashing:** Salted and hashed credentials via passlib.
* **Input Validation:** Strict Pydantic v2 schemas and payload sanitization.
* **Rate Limiting:** IP-based throttles via `slowapi` on auth, AI, and ML endpoints.
* **Content Security Policy (CSP):** `default-src 'none'` API policy.
* **HSTS Headers:** Enforced Strict-Transport-Security.
* **SQL Injection Protection:** Pure SQLAlchemy ORM bindings.
* **Environment Secret Management:** Startup `.env` validation block.
* **Global Exception Handling:** Stack trace redaction and opaque 500 JSON responses.

---

## Testing : 62 Passing

The backend is backed by a robust, 100% passing test suite designed for stability and evaluation compliance.

*   **Unit Tests:** Validating calculators, parsers, and utilities.
*   **Integration Tests:** End-to-end database interactions and auth flows.
*   **Security Tests:** Verifying bcrypt hashing, JWT tampering, and bounds rejection.
*   **ML Tests:** Validating deterministic anomaly detection and positive regression forecasts.
*   **API Tests:** Endpoint contract validation and error handling.

| Category                 | Coverage / Focus                           |
| ------------------------ | ------------------------------------------ |
| TestTransportCalculation | Zero input · petrol vs EV · flights        |
| TestHomeCalculation      | Solar · per-capita scaling                 |
| TestDietCalculation      | Vegan vs omnivore · waste multiplier       |
| TestRatingAndPercentile  | All 5 tiers · monotonicity · bounds        |
| TestFullFootprint        | Total integrity · valid rating             |
| TestMLPrediction         | Determinism · output length · non-negative |
| TestInputValidation      | Negative values · invalid enums            |
| TestSecurity             | bcrypt · JWT roundtrip · tampered token    |
| TestAnomalyDetection     | Spike detection · z-scores · determinism   |
| TestInsightSchemas       | AI request response validation             |
| TestIntegration          | Full request lifecycle, database state     |

---

## Accessibility

The frontend SPA implements inclusive design principles:

* **Semantic HTML5:** Proper heading hierarchy and landmark elements implemented.
* **ARIA Labels:** Interactive elements tagged for screen reader context.
* **Keyboard Navigation:** Tab-index support for forms and dashboard tabs.
* **Responsive Design:** Mobile-first media queries for seamless mobile/desktop usage.
* *Screen Reader Support:* (Standard browser support; advanced custom roles omitted for lightweight design).
* *High Contrast Compatibility:* (Pending explicit high-contrast toggle; native OS inversion supported).

---

## Performance Optimizations

* **SQL query limits:** Capped row fetches (e.g., `limit(1000)`) preventing memory exhaustion.
* **Cached configuration via @lru_cache:** Single-parse environment variable loading.
* **Optimized SQLAlchemy queries:** Minimized N+1 problems via targeted aggregations.
* **Rate-limited AI endpoints:** Prevents API quota exhaustion via Groq.
* **Efficient ML inference:** Lightweight scikit-learn models executed efficiently.
* **Lightweight frontend architecture:** Single-file Vanilla JS SPA minimizes asset payload.

---

## ML Models

### Polynomial Ridge Regression (Trend Forecasting)

- `PolynomialFeatures(degree=2)` + `Ridge(alpha=1.0, random_state=42)`
- Captures realistic reduction curve — rapid early gains then plateau
- Uses real DB history when available, simulated otherwise

### Isolation Forest (Anomaly Detection)

- `IsolationForest(n_estimators=100, contamination=0.15, random_state=42)`
- Trains on user personal history — not global thresholds
- Returns per-category z-scores and human-readable explanation

---

## Emission Factors

| Category          | Factor            | Source               |
| ----------------- | ----------------- | -------------------- |
| Petrol car        | 0.192 kg CO₂e/km  | EPA 2023             |
| EV India grid     | 0.053 kg CO₂e/km  | CEA 2023             |
| Electricity India | 0.716 kg CO₂e/kWh | CEA 2023             |
| Short-haul flight | 255 kg CO₂e/trip  | ICAO                 |
| Long-haul flight  | 1050 kg CO₂e/trip | ICAO                 |
| Vegan diet        | 1500 kg CO₂e/yr   | Poore & Nemecek 2018 |
| Global average    | 4000 kg CO₂e/yr   | IPCC AR6             |
| India average     | 1800 kg CO₂e/yr   | World Bank           |

---

## Tech Stack

| Layer      | Technology                                  |
| ---------- | ------------------------------------------- |
| Backend    | FastAPI · Python 3.11 · Uvicorn             |
| Database   | SQLAlchemy · SQLite                         |
| ML         | scikit-learn · numpy                        |
| AI         | Groq LLaMA 3.1 8B                           |
| Auth       | python-jose · passlib bcrypt                |
| Frontend   | Vanilla JS · Chart.js · BarcodeDetector API |
| Deployment | HuggingFace Spaces · Netlify                |
| Testing    | pytest · 62 tests                           |

---

## License

MIT License : Built for Hack2Skill Challenge 3
