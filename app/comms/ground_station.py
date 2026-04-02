"""
Ground station line-of-sight (LOS) and blackout window calculator.
Checks whether a satellite has visibility to at least one ground station.
"""
import math
import numpy as np
from app.config import RE


def ecef_from_geodetic(lat_deg: float, lon_deg: float, alt_km: float = 0.0) -> np.ndarray:
    """Convert geodetic coordinates to ECEF (Earth-Centered, Earth-Fixed), km."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    r   = RE + alt_km
    return np.array([
        r * math.cos(lat) * math.cos(lon),
        r * math.cos(lat) * math.sin(lon),
        r * math.sin(lat),
    ])


def elevation_angle(sat_eci: np.ndarray, gs_lat: float, gs_lon: float, gs_alt_km: float) -> float:
    """
    Compute elevation angle (degrees) of satellite as seen from a ground station.
    Uses simplified ECI≈ECEF assumption (rotation neglected for short windows).
    """
    gs_pos  = ecef_from_geodetic(gs_lat, gs_lon, gs_alt_km / 1000.0)
    sat_pos = sat_eci[:3]

    to_sat  = sat_pos - gs_pos
    dist    = np.linalg.norm(to_sat)
    if dist < 1e-6:
        return 90.0

    # Zenith unit vector at ground station
    zenith = gs_pos / np.linalg.norm(gs_pos)

    sin_el = np.dot(to_sat, zenith) / dist
    el_deg = math.degrees(math.asin(max(-1.0, min(1.0, sin_el))))
    return el_deg


def has_line_of_sight(
    sat_eci: np.ndarray,
    ground_stations: list[dict],
) -> tuple[bool, str | None]:
    """
    Check if satellite has LOS to at least one ground station.
    Returns (has_los, station_id or None).
    """
    for gs in ground_stations:
        el = elevation_angle(
            sat_eci,
            gs["lat"], gs["lon"],
            gs.get("elevation_m", 0) / 1000.0,
        )
        if el >= gs["min_el_deg"]:
            return True, gs["id"]
    return False, None


def next_los_window(
    sat_state: np.ndarray,
    ground_stations: list[dict],
    max_scan_s: float = 7200.0,
    step_s: float = 30.0,
) -> float | None:
    """
    Scan forward to find next LOS window start time (seconds from now).
    Returns None if no window found within max_scan_s.
    """
    from app.physics.propagator import rk4_step
    state = sat_state.copy()
    t = 0.0
    while t < max_scan_s:
        los, _ = has_line_of_sight(state, ground_stations)
        if los:
            return t
        state = rk4_step(state, step_s)
        t += step_s
    return None
