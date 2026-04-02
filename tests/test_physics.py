"""
Basic smoke tests for AETHER-ACM physics engine and API.
Run with: pytest tests/ -v
"""
import math
import numpy as np
import pytest


def test_propagator_conserves_energy():
    """RK4 propagation should conserve orbital energy within tolerance."""
    from app.physics.propagator import rk4_step
    MU = 398600.4418
    # Circular orbit at 550 km altitude
    r = 6378.137 + 550.0
    v = math.sqrt(MU / r)
    state = np.array([r, 0.0, 0.0, 0.0, v, 0.0])

    def energy(s):
        return 0.5 * np.dot(s[3:], s[3:]) - MU / np.linalg.norm(s[:3])

    E0 = energy(state)
    # Propagate one full orbit (~5800s for 550km)
    for _ in range(200):
        state = rk4_step(state, 30.0)
    E1 = energy(state)
    assert abs((E1 - E0) / E0) < 1e-4, f"Energy drift too large: {abs((E1-E0)/E0):.2e}"


def test_tsiolkovsky():
    """Fuel consumption follows Tsiolkovsky rocket equation."""
    from app.physics.maneuver_planner import tsiolkovsky_fuel
    ISP, G0 = 300.0, 9.80665
    mass = 550.0
    dv_ms = 10.0
    dm = tsiolkovsky_fuel(mass, dv_ms)
    expected = mass * (1 - math.exp(-dv_ms / (ISP * G0)))
    assert abs(dm - expected) < 1e-6


def test_eci_to_latlon():
    """ECI position on equator at prime meridian → lat≈0, lon≈0."""
    from app.physics.propagator import eci_to_latlon
    state = np.array([6928.0, 0.0, 0.0, 0.0, 7.6, 0.0])
    lat, lon, alt = eci_to_latlon(state)
    assert abs(lat) < 1.0
    assert abs(lon) < 5.0
    assert 540 < alt < 560


def test_kd_tree_screening():
    """KD-Tree screening returns candidates within radius."""
    from app.physics.conjunction import screen_conjunctions
    sat_states = {"SAT-A": np.array([7000.0, 0.0, 0.0, 0.0, 7.5, 0.0])}
    # Close debris
    deb_states = {
        "DEB-1": np.array([7000.01, 0.0, 0.0, 0.0, 7.5, 0.0]),   # 10m away — should hit
        "DEB-2": np.array([7100.0, 0.0, 0.0, 0.0, 7.5, 0.0]),    # 100km away — should miss
    }
    candidates = screen_conjunctions(sat_states, deb_states)
    ids = [(s, d) for s, d in candidates]
    assert ("SAT-A", "DEB-1") in ids
    assert ("SAT-A", "DEB-2") not in ids


def test_ground_station_los():
    """IIT Delhi should see a satellite directly overhead."""
    from app.comms.ground_station import elevation_angle
    # Satellite directly above IIT Delhi at 550 km
    import math
    lat, lon = 28.545, 77.193
    r = 6378.137 + 550
    x = r * math.cos(math.radians(lat)) * math.cos(math.radians(lon))
    y = r * math.cos(math.radians(lat)) * math.sin(math.radians(lon))
    z = r * math.sin(math.radians(lat))
    sat_eci = np.array([x, y, z, 0.0, 7.6, 0.0])
    el = elevation_angle(sat_eci, lat, lon, 0.225)
    assert el > 80.0, f"Expected elevation > 80°, got {el:.1f}°"


def test_rtn_to_eci_rotation():
    """Prograde burn in RTN should add velocity in orbital direction."""
    from app.physics.maneuver_planner import rtn_to_eci
    r = np.array([7000.0, 0.0, 0.0])
    v = np.array([0.0, 7.5, 0.0])  # prograde in y direction
    dv_rtn = np.array([0.0, 0.01, 0.0])  # 10 m/s prograde
    dv_eci = rtn_to_eci(dv_rtn, r, v)
    # Should mostly add velocity in y direction
    assert abs(dv_eci[1]) > abs(dv_eci[0])
    assert abs(dv_eci[1]) > abs(dv_eci[2])
