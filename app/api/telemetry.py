"""POST /api/telemetry — ingest state vector updates."""
import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas import TelemetryRequest, TelemetryResponse
from app.autonomy.state_manager import sim_state

router = APIRouter()


@router.post("/telemetry", response_model=TelemetryResponse)
async def ingest_telemetry(payload: TelemetryRequest, db: Session = Depends(get_db)):
    """
    Ingest high-frequency ECI state vectors for satellites and debris.
    Updates in-memory state; DB write is async-friendly (fire-and-forget logging).
    """
    processed = 0
    for obj in payload.objects:
        state = np.array([obj.r.x, obj.r.y, obj.r.z,
                          obj.v.x, obj.v.y, obj.v.z])
        if obj.type.upper() == "SATELLITE":
            fuel = sim_state.sat_fuel.get(obj.id, 50.0)
            sim_state.update_satellite(obj.id, state, fuel)
        else:
            sim_state.update_debris(obj.id, state)
        processed += 1

    return TelemetryResponse(
        status="ACK",
        processed_count=processed,
        active_cdm_warnings=len([c for c in sim_state.active_cdms
                                  if c.get("risk_level") in ("RED", "CRITICAL")]),
    )
