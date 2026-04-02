"""
AETHER-ACM — Autonomous Constellation Manager
FastAPI application entrypoint.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.db.database import init_db, SessionLocal
from app.db.seed import seed_database
from app.autonomy.state_manager import sim_state
from app.api import telemetry, maneuver, simulate, visualization


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB, seed data, load state into memory on startup."""
    print("[AETHER] Initializing database...")
    init_db()
    seed_database()

    print("[AETHER] Loading simulation state...")
    db = SessionLocal()
    try:
        sim_state.load_from_db(db)
    finally:
        db.close()

    print(f"[AETHER] System online. {len(sim_state.satellites)} satellites active.")
    print(f"[AETHER] API ready on http://0.0.0.0:8000")
    yield
    print("[AETHER] Shutting down.")


app = FastAPI(
    title="AETHER-ACM",
    description=(
        "Autonomous Constellation Manager — Orbital Debris Avoidance & "
        "Constellation Management System for the National Space Hackathon 2026."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routes ─────────────────────────────────────────────────────────────
app.include_router(telemetry.router,    prefix="/api", tags=["Telemetry"])
app.include_router(maneuver.router,     prefix="/api", tags=["Maneuver"])
app.include_router(simulate.router,     prefix="/api", tags=["Simulation"])
app.include_router(visualization.router, prefix="/api", tags=["Visualization"])

# ── Static Frontend ────────────────────────────────────────────────────────
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "operational",
        "sim_time": sim_state.sim_time.isoformat(),
        "satellites": len(sim_state.satellites),
        "debris": len(sim_state.debris),
        "health_score": sim_state.health_score(),
    }
