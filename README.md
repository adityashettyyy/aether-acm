# AETHER-ACM

## Autonomous Constellation Manager — National Space Hackathon 2026

---

## Overview

AETHER-ACM is a high-performance autonomous satellite constellation management system designed to detect, predict, and respond to orbital conjunction threats in real time. It manages a fleet of 50+ LEO satellites navigating a debris field of 10,000+ objects — without human intervention.

The system is built around three pillars:

1. **Physics Engine** — RK4 integration with J2 perturbation for accurate orbit propagation  
2. **Conjunction Assessment** — O(N log N) KD-Tree spatial indexing eliminates brute-force O(N²) screening  
3. **Orbital Insight Dashboard** — A startup-grade real-time 2D mission control interface

---

## Architecture

```
aether-acm/
├── Dockerfile                      # ubuntu:22.04 base, exposes port 8000
├── docker-compose.yml
├── requirements.txt
│
├── app/
│   ├── main.py                     # FastAPI entrypoint
│   ├── config.py                   # All physics constants
│   ├── api/
│   │   ├── telemetry.py            # POST /api/telemetry
│   │   ├── maneuver.py             # POST /api/maneuver/schedule
│   │   ├── simulate.py             # POST /api/simulate/step
│   │   └── visualization.py       # GET  /api/visualization/snapshot + extras
│   ├── physics/
│   │   ├── propagator.py           # RK4 + J2 orbital propagator
│   │   ├── conjunction.py          # KD-Tree CA engine + TCA solver
│   │   └── maneuver_planner.py     # RTN frame, ΔV, Tsiolkovsky
│   ├── autonomy/
│   │   ├── state_manager.py        # Thread-safe in-memory state registry
│   │   └── evasion.py              # COLA engine + EOL manager
│   ├── comms/
│   │   └── ground_station.py       # LOS checker + blackout predictor
│   ├── models/
│   │   └── __init__.py             # SQLAlchemy ORM models
│   ├── db/
│   │   ├── database.py             # SQLite engine + session factory
│   │   └── seed.py                 # 50 sats + 5,000 debris in Walker-Delta orbit
│   └── schemas/
│       └── __init__.py             # Pydantic request/response models
│
├── frontend/
│   ├── index.html                  # Single-page Orbital Insight dashboard
│   ├── css/dashboard.css           # Dark mission-control aesthetic
│   └── js/dashboard.js             # Map, bullseye, fuel grid, Gantt, log
│
├── data/
│   └── ground_stations.csv         # 6 global ground stations
│
└── tests/
    └── test_physics.py             # Physics engine smoke tests
```

---

## Quick Start

### Docker (recommended — required for grader)

```bash
# Clone and build
git clone https://github.com/your-team/aether-acm
cd aether-acm

# Build and run
docker build -t aether-acm .
docker run -p 8000:8000 aether-acm

# Or with compose
docker-compose up --build
```

The API will be available at `http://localhost:8000`  
The dashboard will be available at `http://localhost:8000/`  
Swagger docs at `http://localhost:8000/docs`

### Local Development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Initialize and seed DB
python -c "from app.db.database import init_db; init_db()"
python -c "from app.db.seed import seed_database; seed_database()"

# Run
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## API Reference

All endpoints are accessible at `http://localhost:8000/api/`

| Method | Endpoint | Description |
|--------|----------|-------------|

| `POST` | `/api/telemetry` | Ingest ECI state vectors for satellites and debris |
| `POST` | `/api/maneuver/schedule` | Submit and validate a burn sequence |
| `POST` | `/api/simulate/step` | Advance simulation by N seconds |
| `GET`  | `/api/visualization/snapshot` | Optimized dashboard payload |
| `GET`  | `/api/constellation/status` | Fleet health summary |
| `GET`  | `/api/cdm/active` | All active conjunction warnings |
| `GET`  | `/api/maneuver/pending` | Pending burn queue |
| `GET`  | `/api/metrics` | Safety score, fuel, uptime metrics |
| `GET`  | `/health` | System health check |

### Example: Telemetry Ingestion

```bash
curl -X POST http://localhost:8000/api/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-03-12T08:00:00.000Z",
    "objects": [{
      "id": "DEB-99421",
      "type": "DEBRIS",
      "r": {"x": 4500.2, "y": -2100.5, "z": 4800.1},
      "v": {"x": -1.25,  "y": 6.84,    "z": 3.12}
    }]
  }'
```

### Example: Schedule a Maneuver

```bash
curl -X POST http://localhost:8000/api/maneuver/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "satelliteId": "SAT-Alpha-01",
    "maneuver_sequence": [{
      "burn_id": "EVASION_BURN_1",
      "burnTime": "2026-03-12T14:15:30.000Z",
      "deltaV_vector": {"x": 0.002, "y": 0.015, "z": -0.001}
    }]
  }'
```

### Example: Advance Simulation

```bash
curl -X POST http://localhost:8000/api/simulate/step \
  -H "Content-Type: application/json" \
  -d '{"step_seconds": 3600}'
```

---

## Physics Engine

### Orbital Propagation

The propagator integrates the equations of motion using **4th-order Runge-Kutta (RK4)** with a fixed step size of 30 seconds:

```
d²r/dt² = -μ/|r|³ · r + a_J2
```

The **J2 perturbation** accounts for Earth's equatorial bulge:

```
a_J2 = (3/2) · J2 · μ · RE² / |r|⁵ · [x(5z²/|r|² - 1), y(5z²/|r|² - 1), z(5z²/|r|² - 3)]
```

Constants used:

- `μ = 398600.4418 km³/s²`
- `RE = 6378.137 km`
- `J2 = 1.08263 × 10⁻³`

### Conjunction Assessment

The CA pipeline runs in two phases:

**Phase 1 — KD-Tree Screening (O(N log N))**  
All debris positions are indexed in a `scipy.spatial.KDTree`. For each satellite, `query_ball_point(r=50km)` returns candidates without O(N²) pair evaluation.

**Phase 2 — TCA Refinement**  
Candidate pairs are co-propagated with RK4 to find the Time of Closest Approach (TCA). The minimum separation distance determines the risk level:

| Risk Level | Miss Distance |
|------------|---------------|

| GREEN | > 5 km |
| YELLOW | 1–5 km |
| RED | 0.1–1 km |
| CRITICAL | < 100 m |

### Maneuver Planning

Maneuvers are calculated in the **RTN (Radial-Transverse-Normal)** frame and rotated to ECI using:

```
[R̂, T̂, N̂] = [r/|r|, N̂×R̂, (r×v)/|r×v|]
```

**Fuel depletion** follows the **Tsiolkovsky rocket equation**:

```
Δm = m_current · (1 - exp(-|Δv| / (Isp · g₀)))
```

With `Isp = 300 s`, `g₀ = 9.80665 m/s²`, dry mass `500 kg`, initial fuel `50 kg`.

---

## Spacecraft Parameters

| Parameter | Value |
|-----------|-------|

| Dry mass | 500.0 kg |
| Initial fuel mass | 50.0 kg |
| Specific impulse (Isp) | 300.0 s |
| Max ΔV per burn | 15.0 m/s |
| Thruster cooldown | 600 s |
| Signal delay | 10 s |
| Station-keeping box | 10 km radius |
| EOL fuel threshold | 5% |

---

## Ground Station Network

| ID | Station | Lat | Lon | Min Elevation |
|----|---------|-----|-----|---------------|

| GS-001 | ISTRAC Bengaluru | 13.03°N | 77.52°E | 5° |
| GS-002 | Svalbard | 78.23°N | 15.41°E | 5° |
| GS-003 | Goldstone | 35.43°N | 116.89°W | 10° |
| GS-004 | Punta Arenas | 53.15°S | 70.92°W | 5° |
| GS-005 | IIT Delhi | 28.55°N | 77.19°E | 15° |
| GS-006 | McMurdo | 77.85°S | 166.67°E | 5° |

---

## Frontend: Orbital Insight Dashboard

The dashboard is served at `http://localhost:8000/` and includes:

- **Ground Track Map** — Leaflet.js with dark tile layer, real-time satellite markers, orbit trail overlays, debris cloud, and terminator line
- **Conjunction Bullseye** — Canvas polar chart showing debris approach vectors and risk levels
- **Fleet Fuel Heatmap** — 50-cell grid with fuel-proportional color coding
- **Maneuver Gantt** — Timeline showing burn windows, cooldown periods, and blackout zones
- **CDM Alert Table** — Live conjunction warning feed with probability of collision (Pc)
- **System Event Log** — Real-time ACM activity stream
- **SITREP Modal** — One-click mission situation report

---

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

Tests cover: energy conservation in RK4, Tsiolkovsky equation accuracy, ECI↔lat/lon conversion, KD-Tree screening correctness, LOS elevation angle calculation, RTN→ECI rotation.

---

## Evaluation Criteria Mapping

| Criterion | Weight | Our Implementation |
|-----------|--------|--------------------|

| Safety Score | 25% | KD-Tree CA + autonomous COLA engine |
| Fuel Efficiency | 20% | Tsiolkovsky fuel tracking + fleet-wide optimizer |
| Constellation Uptime | 15% | Station-keeping box monitor + recovery burns |
| Algorithmic Speed | 15% | O(N log N) spatial index, async FastAPI |
| UI/UX & Visualization | 15% | Orbital Insight full-screen dark dashboard |
| Code Quality | 10% | Modular architecture, typed schemas, docstrings |

---

## Team

**Team AETHER** — National Space Hackathon 2026, IIT Delhi

---

## License

MIT — Built for National Space Hackathon 2026
