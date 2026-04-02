"""
Seed the database with 50 active satellites and 5,000 debris objects
in realistic LEO orbits. Satellites are in a Walker-Delta constellation
at ~550 km altitude. Debris spans 400–1200 km with varied inclinations.
"""
import math
import random
import uuid
from datetime import datetime, timezone

from app.db.database import SessionLocal
from app.models import Satellite, Debris, GroundStation

random.seed(42)


def _keplerian_to_eci(a, e, inc, raan, argp, nu):
    """Convert Keplerian elements to ECI state vector (km, km/s)."""
    MU = 398600.4418
    p = a * (1 - e**2)
    r_orb = p / (1 + e * math.cos(nu))
    rx_orb = r_orb * math.cos(nu)
    ry_orb = r_orb * math.sin(nu)
    h = math.sqrt(MU * p)
    vx_orb = -MU / h * math.sin(nu)
    vy_orb =  MU / h * (e + math.cos(nu))

    ci, si = math.cos(inc),  math.sin(inc)
    cr, sr = math.cos(raan), math.sin(raan)
    cw, sw = math.cos(argp), math.sin(argp)

    R = [
        [cr*cw - sr*sw*ci,  -cr*sw - sr*cw*ci,  sr*si],
        [sr*cw + cr*sw*ci,  -sr*sw + cr*cw*ci, -cr*si],
        [sw*si,              cw*si,              ci   ],
    ]

    rx = R[0][0]*rx_orb + R[0][1]*ry_orb
    ry = R[1][0]*rx_orb + R[1][1]*ry_orb
    rz = R[2][0]*rx_orb + R[2][1]*ry_orb
    vx = R[0][0]*vx_orb + R[0][1]*vy_orb
    vy = R[1][0]*vx_orb + R[1][1]*vy_orb
    vz = R[2][0]*vx_orb + R[2][1]*vy_orb

    return rx, ry, rz, vx, vy, vz


GROUND_STATIONS = [
    ("GS-001", "ISTRAC_Bengaluru",      13.0333,   77.5167,  820, 5.0),
    ("GS-002", "Svalbard_Sat_Station",  78.2297,   15.4077,  400, 5.0),
    ("GS-003", "Goldstone_Tracking",    35.4266, -116.8900, 1000, 10.0),
    ("GS-004", "Punta_Arenas",         -53.1500,  -70.9167,   30, 5.0),
    ("GS-005", "IIT_Delhi_Ground_Node", 28.5450,   77.1926,  225, 15.0),
    ("GS-006", "McMurdo_Station",      -77.8463,  166.6682,   10, 5.0),
]

SATELLITE_NAMES = [
    "Alpha","Bravo","Charlie","Delta","Echo",
    "Foxtrot","Golf","Hotel","India","Juliet",
]


def seed_database():
    db = SessionLocal()
    try:
        if db.query(Satellite).count() > 0:
            print("[SEED] Database already seeded. Skipping.")
            return

        # ── Ground Stations ──────────────────────────────────────────────
        for gs_id, name, lat, lon, elev, min_el in GROUND_STATIONS:
            db.merge(GroundStation(
                id=gs_id, name=name, lat=lat, lon=lon,
                elevation_m=elev, min_el_deg=min_el
            ))

        # ── 50 Satellites in Walker-Delta constellation at ~550 km ───────
        RE = 6378.137
        a_sat = RE + 550.0
        inc_sat = math.radians(53.0)
        sat_count = 0
        for plane in range(10):
            raan = math.radians(plane * 36.0)
            for seat in range(5):
                nu = math.radians(seat * 72.0 + plane * 36.0)
                rx, ry, rz, vx, vy, vz = _keplerian_to_eci(
                    a_sat, 0.0001, inc_sat, raan, 0.0, nu
                )
                group = SATELLITE_NAMES[plane % len(SATELLITE_NAMES)]
                sat_id = f"SAT-{group}-{seat+1:02d}"
                fuel = 50.0 - random.uniform(0, 8.0)
                db.add(Satellite(
                    id=sat_id,
                    mass_kg=500.0 + fuel,
                    fuel_kg=fuel,
                    pos_x=rx, pos_y=ry, pos_z=rz,
                    vel_x=vx, vel_y=vy, vel_z=vz,
                    slot_x=rx, slot_y=ry, slot_z=rz,
                    status="NOMINAL",
                    updated_at=datetime.now(timezone.utc),
                ))
                sat_count += 1

        # ── 5,000 Debris objects spread across LEO ───────────────────────
        debris_count = 0
        for i in range(5000):
            alt = random.uniform(400, 1200)
            a_deb = RE + alt
            inc = math.radians(random.uniform(0, 98))
            raan = math.radians(random.uniform(0, 360))
            argp = math.radians(random.uniform(0, 360))
            nu   = math.radians(random.uniform(0, 360))
            e    = random.uniform(0.0, 0.02)
            rx, ry, rz, vx, vy, vz = _keplerian_to_eci(a_deb, e, inc, raan, argp, nu)
            db.add(Debris(
                id=f"DEB-{90000+i}",
                pos_x=rx, pos_y=ry, pos_z=rz,
                vel_x=vx, vel_y=vy, vel_z=vz,
                updated_at=datetime.now(timezone.utc),
            ))
            debris_count += 1

        db.commit()
        print(f"[SEED] {sat_count} satellites + {debris_count} debris objects seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    from app.db.database import init_db
    init_db()
    seed_database()
