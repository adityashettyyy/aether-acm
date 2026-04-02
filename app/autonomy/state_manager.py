"""
Simulation State Manager — central in-memory registry for all object states.
Provides fast access to current ECI states without repeated DB reads.
"""
import numpy as np
from datetime import datetime, timezone
from threading import Lock
from app.config import SIM_START_TIME


class SimulationState:
    """Thread-safe in-memory state for physics engine."""

    def __init__(self):
        self._lock = Lock()
        self.sim_time: datetime = SIM_START_TIME
        self.satellites: dict[str, np.ndarray] = {}   # id → [x,y,z,vx,vy,vz]
        self.debris: dict[str, np.ndarray]     = {}   # id → [x,y,z,vx,vy,vz]
        self.sat_fuel: dict[str, float]        = {}   # id → fuel_kg
        self.sat_mass: dict[str, float]        = {}   # id → total mass_kg
        self.sat_slots: dict[str, np.ndarray]  = {}   # id → nominal slot ECI
        self.sat_status: dict[str, str]        = {}   # id → status string
        self.pending_burns: list[dict]         = []   # scheduled maneuvers
        self.active_cdms: list[dict]           = []   # current CDM list
        self.ground_stations: list[dict]       = []   # GS dicts

    def load_from_db(self, db):
        """Initialize state from database on startup."""
        from app.models import Satellite, Debris, GroundStation
        with self._lock:
            for sat in db.query(Satellite).all():
                state = np.array([sat.pos_x, sat.pos_y, sat.pos_z,
                                   sat.vel_x, sat.vel_y, sat.vel_z])
                self.satellites[sat.id] = state
                self.sat_fuel[sat.id]   = sat.fuel_kg
                self.sat_mass[sat.id]   = sat.mass_kg
                self.sat_slots[sat.id]  = np.array([sat.slot_x, sat.slot_y, sat.slot_z,
                                                     sat.vel_x, sat.vel_y, sat.vel_z])
                self.sat_status[sat.id] = sat.status

            for deb in db.query(Debris).all():
                self.debris[deb.id] = np.array([
                    deb.pos_x, deb.pos_y, deb.pos_z,
                    deb.vel_x, deb.vel_y, deb.vel_z,
                ])

            for gs in db.query(GroundStation).all():
                self.ground_stations.append({
                    "id": gs.id, "name": gs.name,
                    "lat": gs.lat, "lon": gs.lon,
                    "elevation_m": gs.elevation_m,
                    "min_el_deg": gs.min_el_deg,
                })

        print(f"[STATE] Loaded {len(self.satellites)} satellites, "
              f"{len(self.debris)} debris, {len(self.ground_stations)} GS.")

    def update_satellite(self, sat_id: str, state: np.ndarray,
                          fuel_kg: float = None, status: str = None):
        with self._lock:
            self.satellites[sat_id] = state
            if fuel_kg is not None:
                self.sat_fuel[sat_id] = fuel_kg
                self.sat_mass[sat_id] = 500.0 + fuel_kg
            if status:
                self.sat_status[sat_id] = status

    def update_debris(self, deb_id: str, state: np.ndarray):
        with self._lock:
            self.debris[deb_id] = state

    def health_score(self) -> float:
        """Composite fleet health 0-100."""
        if not self.satellites:
            return 100.0
        nominal = sum(1 for s in self.sat_status.values() if s == "NOMINAL")
        uptime  = nominal / len(self.satellites)
        avg_fuel = (sum(self.sat_fuel.values()) /
                    (len(self.sat_fuel) * 50.0)) if self.sat_fuel else 1.0
        safe    = max(0, 1 - len(self.active_cdms) / max(1, len(self.satellites)))
        return round((0.4 * uptime + 0.3 * min(1.0, avg_fuel) + 0.3 * safe) * 100, 1)


# Global singleton
sim_state = SimulationState()
