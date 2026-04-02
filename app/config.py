"""
AETHER-ACM — Physics & Mission Constants
All simulation parameters, thresholds, and spacecraft properties.
"""

# ── Earth & Orbital Mechanics ──────────────────────────────────────────────
MU = 398600.4418          # Earth gravitational parameter, km³/s²
RE = 6378.137             # Earth equatorial radius, km
J2 = 1.08263e-3           # J2 zonal harmonic coefficient
OMEGA_EARTH = 7.2921150e-5  # Earth rotation rate, rad/s

# ── Spacecraft Properties (identical for all sats) ─────────────────────────
DRY_MASS_KG    = 500.0    # Dry mass, kg
FUEL_MASS_KG   = 50.0     # Initial propellant mass, kg
WET_MASS_KG    = 550.0    # Total initial mass, kg
ISP            = 300.0    # Specific impulse, s
G0             = 9.80665  # Standard gravity, m/s²
MAX_DV_MS      = 15.0     # Max ΔV per burn, m/s
COOLDOWN_S     = 600.0    # Mandatory thruster cooldown, s
SIGNAL_DELAY_S = 10.0     # Command uplink latency, s

# ── Mission Thresholds ─────────────────────────────────────────────────────
COLLISION_DIST_KM     = 0.100   # Critical miss distance, km (100m)
STATION_KEEP_BOX_KM   = 10.0   # Nominal slot tolerance radius, km
FUEL_EOL_THRESHOLD    = 0.05   # End-of-life fuel fraction (5%)
CDM_WARNING_KM        = 5.0    # Yellow CDM threshold, km
CDM_CRITICAL_KM       = 1.0    # Red CDM threshold, km
CONJUNCTION_HORIZON_H = 24     # Lookahead window, hours
SPATIAL_SCREEN_KM     = 50.0   # KD-Tree first-pass screening radius, km

# ── Propagation ───────────────────────────────────────────────────────────
RK4_STEP_S    = 30.0      # RK4 integration step size, s
MAX_TICK_S    = 86400     # Max simulation tick, s (24h)

# ── Simulation State ───────────────────────────────────────────────────────
import datetime
SIM_START_TIME = datetime.datetime(2026, 3, 12, 8, 0, 0, tzinfo=datetime.timezone.utc)
