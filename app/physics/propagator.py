"""
Orbital propagator: RK4 integration with J2 perturbation.
Propagates ECI state vectors [x,y,z,vx,vy,vz] (km, km/s) forward in time.
"""
import math
import numpy as np
from app.config import MU, RE, J2, RK4_STEP_S


def j2_acceleration(r: np.ndarray) -> np.ndarray:
    """
    Compute J2 perturbation acceleration vector in ECI frame.
    r: position vector [x, y, z] in km
    returns: acceleration [ax, ay, az] in km/s²
    """
    x, y, z = r
    r_mag = np.linalg.norm(r)
    if r_mag < 1.0:
        return np.zeros(3)

    factor = 1.5 * J2 * MU * RE**2 / r_mag**5
    z2_r2 = (z / r_mag)**2

    ax = factor * x * (5.0 * z2_r2 - 1.0)
    ay = factor * y * (5.0 * z2_r2 - 1.0)
    az = factor * z * (5.0 * z2_r2 - 3.0)
    return np.array([ax, ay, az])


def equations_of_motion(state: np.ndarray) -> np.ndarray:
    """
    Compute state derivative [vx, vy, vz, ax, ay, az].
    state: [x, y, z, vx, vy, vz] km, km/s
    """
    r = state[:3]
    v = state[3:]
    r_mag = np.linalg.norm(r)
    if r_mag < RE * 0.9:
        # Below atmosphere — degenerate state, return zeros to avoid NaN
        return np.zeros(6)

    a_grav = -MU / r_mag**3 * r
    a_j2   = j2_acceleration(r)
    a_total = a_grav + a_j2

    return np.concatenate([v, a_total])


def rk4_step(state: np.ndarray, dt: float) -> np.ndarray:
    """Single RK4 integration step."""
    k1 = equations_of_motion(state)
    k2 = equations_of_motion(state + 0.5 * dt * k1)
    k3 = equations_of_motion(state + 0.5 * dt * k2)
    k4 = equations_of_motion(state + dt * k3)
    return state + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)


def propagate(state: np.ndarray, duration_s: float, step_s: float = RK4_STEP_S) -> np.ndarray:
    """
    Propagate state vector forward by duration_s seconds.
    Returns final state [x,y,z,vx,vy,vz].
    """
    t = 0.0
    while t < duration_s:
        dt = min(step_s, duration_s - t)
        state = rk4_step(state, dt)
        # NaN guard
        if np.any(np.isnan(state)) or np.any(np.isinf(state)):
            break
        t += dt
    return state


def propagate_trajectory(
    state: np.ndarray, duration_s: float, step_s: float = 60.0
) -> list[np.ndarray]:
    """
    Return a list of state vectors sampled every step_s seconds.
    Used for orbit trail and prediction line rendering.
    """
    trajectory = [state.copy()]
    t = 0.0
    current = state.copy()
    while t < duration_s:
        dt = min(step_s, duration_s - t)
        current = rk4_step(current, dt)
        if np.any(np.isnan(current)):
            break
        trajectory.append(current.copy())
        t += dt
    return trajectory


def eci_to_latlon(state: np.ndarray, gmst: float = 0.0) -> tuple[float, float, float]:
    """
    Convert ECI position to geodetic lat/lon/alt.
    gmst: Greenwich Mean Sidereal Time in radians (0 for simplification).
    Returns (lat_deg, lon_deg, alt_km).
    """
    x, y, z = state[:3]
    r = math.sqrt(x**2 + y**2 + z**2)
    lat = math.degrees(math.asin(z / r))
    lon = math.degrees(math.atan2(y, x)) - math.degrees(gmst)
    lon = ((lon + 180) % 360) - 180
    alt = r - RE
    return lat, lon, alt
