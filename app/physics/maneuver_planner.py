"""
Maneuver planning engine.
Calculates optimal evasion ΔV in RTN frame, converts to ECI,
applies Tsiolkovsky rocket equation for fuel bookkeeping.
"""
import math
import numpy as np
from app.config import ISP, G0, DRY_MASS_KG, COLLISION_DIST_KM, MAX_DV_MS


def rtn_to_eci(dv_rtn: np.ndarray, r: np.ndarray, v: np.ndarray) -> np.ndarray:
    """
    Rotate ΔV vector from RTN (Radial-Transverse-Normal) to ECI frame.
    r, v: ECI position and velocity (km, km/s)
    dv_rtn: [dR, dT, dN] km/s
    """
    r_hat = r / np.linalg.norm(r)
    h     = np.cross(r, v)
    n_hat = h / np.linalg.norm(h)
    t_hat = np.cross(n_hat, r_hat)

    # Rotation matrix: columns are RTN unit vectors
    R = np.column_stack([r_hat, t_hat, n_hat])
    return R @ dv_rtn


def tsiolkovsky_fuel(mass_kg: float, dv_ms: float) -> float:
    """
    Mass of propellant consumed for a given ΔV (m/s).
    ΔV is in m/s, returns kg consumed.
    """
    ve = ISP * G0  # effective exhaust velocity, m/s
    delta_m = mass_kg * (1.0 - math.exp(-dv_ms / ve))
    return max(0.0, delta_m)


def plan_evasion_burn(
    sat_state: np.ndarray,
    deb_state: np.ndarray,
    miss_dist_km: float,
    fuel_kg: float,
) -> np.ndarray | None:
    """
    Compute a prograde/retrograde evasion ΔV in RTN frame.
    Strategy: prograde burn to increase semi-major axis and phase away.
    Returns ΔV vector in ECI (km/s) or None if insufficient fuel.
    """
    r = sat_state[:3]
    v = sat_state[3:]

    # Scale evasion magnitude to threat severity
    # Critical (<100m): use max allowable burn
    # Yellow (<5km): smaller correction
    if miss_dist_km < COLLISION_DIST_KM:
        dv_ms = min(MAX_DV_MS, 5.0)
    elif miss_dist_km < 1.0:
        dv_ms = min(MAX_DV_MS * 0.6, 3.0)
    else:
        dv_ms = min(MAX_DV_MS * 0.3, 1.5)

    total_mass = DRY_MASS_KG + fuel_kg
    fuel_needed = tsiolkovsky_fuel(total_mass, dv_ms)

    if fuel_kg < fuel_needed * 1.05:  # 5% safety margin
        return None

    # Prograde burn (positive Transverse direction)
    dv_rtn = np.array([0.0, dv_ms / 1000.0, 0.0])  # convert m/s → km/s
    return rtn_to_eci(dv_rtn, r, v)


def plan_recovery_burn(
    sat_state: np.ndarray,
    slot_state: np.ndarray,
    fuel_kg: float,
) -> np.ndarray | None:
    """
    Compute retrograde recovery burn to return satellite to its slot.
    Uses relative velocity matching as a simplified homing strategy.
    """
    r = sat_state[:3]
    v = sat_state[3:]

    pos_error = slot_state[:3] - r
    dist_km   = np.linalg.norm(pos_error)

    if dist_km < 0.5:
        return None  # Already close enough

    # Gentle retrograde correction, scaled to distance
    dv_ms = min(MAX_DV_MS * 0.4, dist_km * 0.05, 2.0)
    total_mass = DRY_MASS_KG + fuel_kg
    fuel_needed = tsiolkovsky_fuel(total_mass, dv_ms)

    if fuel_kg < fuel_needed * 1.05:
        return None

    # Retrograde burn
    dv_rtn = np.array([0.0, -dv_ms / 1000.0, 0.0])
    return rtn_to_eci(dv_rtn, r, v)


def apply_burn(
    state: np.ndarray,
    fuel_kg: float,
    dv_eci: np.ndarray,
) -> tuple[np.ndarray, float, float]:
    """
    Apply impulsive burn to state vector.
    Returns (new_state, fuel_consumed_kg, new_fuel_kg).
    """
    dv_ms  = np.linalg.norm(dv_eci) * 1000.0  # km/s → m/s
    total  = DRY_MASS_KG + fuel_kg
    burned = tsiolkovsky_fuel(total, dv_ms)

    new_state    = state.copy()
    new_state[3:] += dv_eci  # instantaneous ΔV
    new_fuel     = max(0.0, fuel_kg - burned)

    return new_state, burned, new_fuel
