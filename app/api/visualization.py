"""GET /api/visualization/snapshot and supporting status endpoints."""
import math
import numpy as np
from fastapi import APIRouter
from app.schemas import SnapshotResponse, SatVizItem, ConstellationStatus
from app.autonomy.state_manager import sim_state
from app.physics.propagator import eci_to_latlon

router = APIRouter()


@router.get("/visualization/snapshot", response_model=SnapshotResponse)
async def get_snapshot():
    """
    Optimized payload for the Orbital Insight dashboard.
    Uses tuple-based debris array for minimal JSON size.
    """
    satellites = []
    sat_risk = {c["satellite_id"]: c["risk_level"] for c in sim_state.active_cdms}

    for sat_id, state in sim_state.satellites.items():
        lat, lon, alt = eci_to_latlon(state)
        fuel = sim_state.sat_fuel.get(sat_id, 0.0)
        satellites.append(SatVizItem(
            id=sat_id,
            lat=round(lat, 4),
            lon=round(lon, 4),
            alt=round(alt, 1),
            fuel_kg=round(fuel, 2),
            fuel_pct=round(fuel / 50.0 * 100, 1),
            status=sim_state.sat_status.get(sat_id, "NOMINAL"),
            risk_level=sat_risk.get(sat_id, "GREEN"),
        ))

    # Debris as flat tuples [id, lat, lon, alt] — compact JSON
    debris_cloud = []
    for deb_id, state in list(sim_state.debris.items())[:5000]:
        lat, lon, alt = eci_to_latlon(state)
        debris_cloud.append([deb_id, round(lat, 2), round(lon, 2), round(alt, 0)])

    recent_cdms = [
        {
            "id": c["id"],
            "satellite_id": c["satellite_id"],
            "debris_id": c["debris_id"],
            "tca": c["tca"].isoformat(),
            "miss_dist_km": c["miss_dist_km"],
            "risk_level": c["risk_level"],
        }
        for c in sim_state.active_cdms[:50]
    ]

    return SnapshotResponse(
        timestamp=sim_state.sim_time,
        health_score=sim_state.health_score(),
        active_cdms=len(sim_state.active_cdms),
        satellites=satellites,
        debris_cloud=debris_cloud,
        recent_cdms=recent_cdms,
    )


@router.get("/constellation/status", response_model=ConstellationStatus)
async def get_status():
    nominal = sum(1 for s in sim_state.sat_status.values() if s == "NOMINAL")
    avg_fuel = (sum(sim_state.sat_fuel.values()) / max(1, len(sim_state.sat_fuel)))
    return ConstellationStatus(
        satellite_count=len(sim_state.satellites),
        debris_count=len(sim_state.debris),
        active_cdm_count=len(sim_state.active_cdms),
        health_score=sim_state.health_score(),
        sim_time=sim_state.sim_time,
        avg_fuel_pct=round(avg_fuel / 50.0 * 100, 1),
        nominal_count=nominal,
    )


@router.get("/cdm/active")
async def get_active_cdms():
    return {"cdms": sim_state.active_cdms[:50], "total": len(sim_state.active_cdms)}


@router.get("/maneuver/pending")
async def get_pending_maneuvers():
    burns = []
    for b in sim_state.pending_burns[:100]:
        burns.append({
            "id": b["id"],
            "satellite_id": b["satellite_id"],
            "burn_id": b.get("burn_id", ""),
            "burn_time": b["burn_time"].isoformat(),
            "dv_magnitude_ms": round(
                np.linalg.norm([b["dv_x"], b["dv_y"], b["dv_z"]]) * 1000.0, 3
            ),
            "status": "PENDING",
        })
    return {"burns": burns, "total": len(sim_state.pending_burns)}


@router.get("/metrics")
async def get_metrics():
    return {
        "health_score": sim_state.health_score(),
        "total_satellites": len(sim_state.satellites),
        "nominal": sum(1 for s in sim_state.sat_status.values() if s == "NOMINAL"),
        "evading": sum(1 for s in sim_state.sat_status.values() if s == "EVADING"),
        "recovery": sum(1 for s in sim_state.sat_status.values() if s == "RECOVERY"),
        "eol": sum(1 for s in sim_state.sat_status.values() if s == "EOL"),
        "active_cdms": len(sim_state.active_cdms),
        "critical_cdms": sum(1 for c in sim_state.active_cdms if c["risk_level"] == "CRITICAL"),
        "pending_burns": len(sim_state.pending_burns),
        "avg_fuel_pct": round(
            sum(sim_state.sat_fuel.values()) / max(1, len(sim_state.sat_fuel)) / 50.0 * 100, 1
        ),
    }
