"""
COLA — Collision Avoidance Engine.
Monitors CDMs and autonomously schedules evasion + recovery maneuver pairs.
"""
import uuid
import numpy as np
from datetime import datetime, timedelta, timezone

from app.config import SIGNAL_DELAY_S, COOLDOWN_S, FUEL_EOL_THRESHOLD, DRY_MASS_KG
from app.physics.maneuver_planner import plan_evasion_burn, plan_recovery_burn


def auto_evade(sim_state, cdm: dict) -> list[dict]:
    """
    Given a CDM, calculate and schedule evasion + recovery burn pair.
    Returns list of burn dicts ready for DB insertion.
    """
    sat_id   = cdm["satellite_id"]
    sat_st   = sim_state.satellites.get(sat_id)
    deb_st   = sim_state.debris.get(cdm["debris_id"])
    fuel_kg  = sim_state.sat_fuel.get(sat_id, 0.0)
    sim_time = sim_state.sim_time

    if sat_st is None or deb_st is None:
        return []

    # EOL check — don't schedule burns if too little fuel
    fuel_frac = fuel_kg / 50.0
    if fuel_frac < FUEL_EOL_THRESHOLD:
        return []

    # ── Evasion burn ─────────────────────────────────────────────────────
    dv_evade = plan_evasion_burn(sat_st, deb_st, cdm["miss_dist_km"], fuel_kg)
    if dv_evade is None:
        return []

    burn_time_evade = sim_time + timedelta(seconds=SIGNAL_DELAY_S + 30)

    # ── Recovery burn (90 min later — one orbital period ~90 min for LEO) ─
    slot_st  = sim_state.sat_slots.get(sat_id, sat_st)
    dv_recov = plan_recovery_burn(sat_st, slot_st, fuel_kg)

    burns = [{
        "id":           str(uuid.uuid4()),
        "satellite_id": sat_id,
        "burn_id":      f"EVADE_{cdm['id'][:8]}",
        "burn_time":    burn_time_evade,
        "dv_x": dv_evade[0], "dv_y": dv_evade[1], "dv_z": dv_evade[2],
        "status":       "PENDING",
        "cdm_id":       cdm["id"],
    }]

    if dv_recov is not None:
        burn_time_recov = burn_time_evade + timedelta(seconds=COOLDOWN_S + 5400)
        burns.append({
            "id":           str(uuid.uuid4()),
            "satellite_id": sat_id,
            "burn_id":      f"RECOV_{cdm['id'][:8]}",
            "burn_time":    burn_time_recov,
            "dv_x": dv_recov[0], "dv_y": dv_recov[1], "dv_z": dv_recov[2],
            "status":       "PENDING",
            "cdm_id":       cdm["id"],
        })

    return burns


def check_eol_and_graveyard(sim_state) -> list[dict]:
    """
    Detect fuel-critical satellites and schedule graveyard deorbit.
    Graveyard orbit: retrograde burn to lower perigee below 300 km.
    """
    burns = []
    for sat_id, fuel_kg in sim_state.sat_fuel.items():
        if fuel_kg / 50.0 > FUEL_EOL_THRESHOLD * 1.2:
            continue
        sat_st = sim_state.satellites.get(sat_id)
        if sat_st is None:
            continue
        # Strong retrograde burn to deorbit
        import numpy as np
        from app.config import MAX_DV_MS
        v = sat_st[3:]
        v_hat = v / np.linalg.norm(v)
        dv = -v_hat * (MAX_DV_MS * 0.8 / 1000.0)  # km/s

        burns.append({
            "id":           str(uuid.uuid4()),
            "satellite_id": sat_id,
            "burn_id":      f"EOL_DEORBIT",
            "burn_time":    sim_state.sim_time + timedelta(seconds=SIGNAL_DELAY_S + 60),
            "dv_x": dv[0], "dv_y": dv[1], "dv_z": dv[2],
            "status":       "PENDING",
        })
        sim_state.sat_status[sat_id] = "EOL"

    return burns
