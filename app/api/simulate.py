"""POST /api/simulate/step — advance simulation time and execute physics."""
import numpy as np
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas import StepRequest, StepResponse
from app.autonomy.state_manager import sim_state
from app.physics.propagator import propagate
from app.physics.conjunction import run_conjunction_assessment
from app.physics.maneuver_planner import apply_burn
from app.autonomy.evasion import auto_evade, check_eol_and_graveyard
from app.config import MAX_TICK_S, STATION_KEEP_BOX_KM, COLLISION_DIST_KM
from app.models import ManeuverCommand, EventLog, CDM

router = APIRouter()


@router.post("/simulate/step", response_model=StepResponse)
async def simulate_step(payload: StepRequest, db: Session = Depends(get_db)):
    step_s = min(payload.step_seconds, MAX_TICK_S)
    collisions_detected = 0
    maneuvers_executed  = 0

    # ── 1. Propagate all objects ──────────────────────────────────────────
    for sat_id, state in list(sim_state.satellites.items()):
        new_state = propagate(state, step_s)
        sim_state.satellites[sat_id] = new_state

    for deb_id, state in list(sim_state.debris.items()):
        new_state = propagate(state, step_s)
        sim_state.debris[deb_id] = new_state

    # ── 2. Execute scheduled burns within this tick window ────────────────
    new_time = sim_state.sim_time + timedelta(seconds=step_s)
    executed_ids = []
    for burn in list(sim_state.pending_burns):
        bt = burn["burn_time"]
        if bt.tzinfo is None:
            bt = bt.replace(tzinfo=timezone.utc)
        if sim_state.sim_time <= bt <= new_time:
            sat_id = burn["satellite_id"]
            sat_st = sim_state.satellites.get(sat_id)
            fuel   = sim_state.sat_fuel.get(sat_id, 0.0)
            if sat_st is None:
                continue
            dv = np.array([burn["dv_x"], burn["dv_y"], burn["dv_z"]])
            new_st, burned, new_fuel = apply_burn(sat_st, fuel, dv)
            sim_state.update_satellite(sat_id, new_st, new_fuel)
            maneuvers_executed += 1
            executed_ids.append(burn["id"])

            # Update DB
            db_burn = db.query(ManeuverCommand).filter_by(id=burn["id"]).first()
            if db_burn:
                db_burn.status           = "EXECUTED"
                db_burn.fuel_consumed_kg = round(burned, 4)

    sim_state.pending_burns = [b for b in sim_state.pending_burns
                                 if b["id"] not in executed_ids]

    # ── 3. Update sim time ────────────────────────────────────────────────
    sim_state.sim_time = new_time

    # ── 4. Conjunction assessment (every tick) ────────────────────────────
    cdms = run_conjunction_assessment(
        sim_state.satellites,
        sim_state.debris,
        sim_state.sim_time,
        horizon_h=12,  # Faster window for tick efficiency
    )
    sim_state.active_cdms = cdms

    # Check for actual collisions
    for cdm in cdms:
        if cdm["miss_dist_km"] < COLLISION_DIST_KM:
            collisions_detected += 1

    # ── 5. Autonomous evasion scheduling ─────────────────────────────────
    for cdm in cdms[:5]:  # Top 5 threats
        sat_id = cdm["satellite_id"]
        # Skip if burns already scheduled for this satellite
        already = any(b["satellite_id"] == sat_id for b in sim_state.pending_burns)
        if not already:
            new_burns = auto_evade(sim_state, cdm)
            for burn in new_burns:
                sim_state.pending_burns.append(burn)
                sim_state.sat_status[sat_id] = "EVADING"
                print(f"[AUTO] {sat_id} → EVADING due to {cdm['miss_dist_km']} km threat")
                db.add(ManeuverCommand(
                    id=burn["id"],
                    satellite_id=burn["satellite_id"],
                    burn_id=burn["burn_id"],
                    burn_time=burn["burn_time"],
                    dv_x=burn["dv_x"], dv_y=burn["dv_y"], dv_z=burn["dv_z"],
                    status="PENDING",
                ))

            # Persist CDM
            db.add(CDM(
                id=cdm["id"],
                satellite_id=cdm["satellite_id"],
                debris_id=cdm["debris_id"],
                tca=cdm["tca"],
                miss_dist_km=cdm["miss_dist_km"],
                risk_level=cdm["risk_level"],
            ))

    # ── 6. Station-keeping status update ─────────────────────────────────
    for sat_id, sat_st in sim_state.satellites.items():
        slot = sim_state.sat_slots.get(sat_id)
        if slot is None:
            continue
        dist = np.linalg.norm(sat_st[:3] - slot[:3])
        current_status = sim_state.sat_status.get(sat_id, "NOMINAL")
        if dist > STATION_KEEP_BOX_KM and current_status == "NOMINAL":
            sim_state.sat_status[sat_id] = "RECOVERY"
        elif dist <= STATION_KEEP_BOX_KM and current_status == "RECOVERY":
            sim_state.sat_status[sat_id] = "NOMINAL"

    # ── 7. EOL check ──────────────────────────────────────────────────────
    eol_burns = check_eol_and_graveyard(sim_state)
    for burn in eol_burns:
        sim_state.pending_burns.append(burn)

    db.commit()

    return StepResponse(
        status="STEP_COMPLETE",
        new_timestamp=sim_state.sim_time,
        collisions_detected=collisions_detected,
        maneuvers_executed=maneuvers_executed,
    )
