"""POST /api/maneuver/schedule — validate and schedule burn sequences."""
import uuid
import numpy as np
from datetime import timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas import ManeuverRequest, ManeuverResponse, ManeuverValidation
from app.autonomy.state_manager import sim_state
from app.comms.ground_station import has_line_of_sight
from app.physics.maneuver_planner import tsiolkovsky_fuel
from app.config import SIGNAL_DELAY_S, DRY_MASS_KG, MAX_DV_MS
from app.models import ManeuverCommand

router = APIRouter()


@router.post("/maneuver/schedule", response_model=ManeuverResponse)
async def schedule_maneuver(payload: ManeuverRequest, db: Session = Depends(get_db)):
    sat_id = payload.satelliteId
    sat_st = sim_state.satellites.get(sat_id)
    fuel   = sim_state.sat_fuel.get(sat_id, 0.0)

    if sat_st is None:
        raise HTTPException(status_code=404, detail=f"Satellite {sat_id} not found")

    # ── LOS check on first burn ──────────────────────────────────────────
    first_burn = payload.maneuver_sequence[0]
    los, gs_id = has_line_of_sight(sat_st, sim_state.ground_stations)

    # ── Fuel sufficiency check ────────────────────────────────────────────
    total_dv_ms = 0.0
    for burn in payload.maneuver_sequence:
        dv = burn.deltaV_vector
        mag = np.linalg.norm([dv.x, dv.y, dv.z]) * 1000.0  # km/s → m/s
        if mag > MAX_DV_MS:
            raise HTTPException(
                status_code=400,
                detail=f"Burn {burn.burn_id} exceeds MAX_DV ({MAX_DV_MS} m/s)"
            )
        total_dv_ms += mag

    mass = DRY_MASS_KG + fuel
    total_fuel_needed = tsiolkovsky_fuel(mass, total_dv_ms)
    sufficient_fuel   = fuel >= total_fuel_needed

    # ── Signal delay check ────────────────────────────────────────────────
    sim_t = sim_state.sim_time
    burn_t = first_burn.burnTime
    if burn_t.tzinfo is None:
        burn_t = burn_t.replace(tzinfo=timezone.utc)
    if (burn_t - sim_t).total_seconds() < SIGNAL_DELAY_S:
        raise HTTPException(
            status_code=400,
            detail=f"Burn scheduled too soon — minimum {SIGNAL_DELAY_S}s signal delay required"
        )

    # ── Persist to DB ─────────────────────────────────────────────────────
    if los and sufficient_fuel:
        for burn in payload.maneuver_sequence:
            dv = burn.deltaV_vector
            bt = burn.burnTime
            if bt.tzinfo is None:
                bt = bt.replace(tzinfo=timezone.utc)
            cmd = ManeuverCommand(
                id=str(uuid.uuid4()),
                satellite_id=sat_id,
                burn_id=burn.burn_id,
                burn_time=bt,
                dv_x=dv.x, dv_y=dv.y, dv_z=dv.z,
                status="PENDING",
            )
            db.add(cmd)
            sim_state.pending_burns.append({
                "id": cmd.id, "satellite_id": sat_id,
                "burn_time": bt,
                "dv_x": dv.x, "dv_y": dv.y, "dv_z": dv.z,
            })
        db.commit()

    proj_mass = DRY_MASS_KG + max(0.0, fuel - total_fuel_needed)

    return ManeuverResponse(
        status="SCHEDULED" if (los and sufficient_fuel) else "REJECTED",
        validation=ManeuverValidation(
            ground_station_los=los,
            sufficient_fuel=sufficient_fuel,
            projected_mass_remaining_kg=round(proj_mass, 2),
        ),
    )
