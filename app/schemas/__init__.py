"""Pydantic request/response schemas for all API endpoints."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel


# ── Telemetry ──────────────────────────────────────────────────────────────
class Vec3(BaseModel):
    x: float
    y: float
    z: float


class TelemetryObject(BaseModel):
    id: str
    type: str   # "SATELLITE" or "DEBRIS"
    r: Vec3
    v: Vec3


class TelemetryRequest(BaseModel):
    timestamp: datetime
    objects: list[TelemetryObject]


class TelemetryResponse(BaseModel):
    status: str
    processed_count: int
    active_cdm_warnings: int


# ── Maneuver ───────────────────────────────────────────────────────────────
class BurnCommand(BaseModel):
    burn_id: str
    burnTime: datetime
    deltaV_vector: Vec3


class ManeuverRequest(BaseModel):
    satelliteId: str
    maneuver_sequence: list[BurnCommand]


class ManeuverValidation(BaseModel):
    ground_station_los: bool
    sufficient_fuel: bool
    projected_mass_remaining_kg: float


class ManeuverResponse(BaseModel):
    status: str
    validation: ManeuverValidation


# ── Simulation Step ────────────────────────────────────────────────────────
class StepRequest(BaseModel):
    step_seconds: int


class StepResponse(BaseModel):
    status: str
    new_timestamp: datetime
    collisions_detected: int
    maneuvers_executed: int


# ── Visualization ──────────────────────────────────────────────────────────
class SatVizItem(BaseModel):
    id: str
    lat: float
    lon: float
    alt: float
    fuel_kg: float
    fuel_pct: float
    status: str
    risk_level: str


class SnapshotResponse(BaseModel):
    timestamp: datetime
    health_score: float
    active_cdms: int
    satellites: list[SatVizItem]
    debris_cloud: list[list]   # [id, lat, lon, alt]
    recent_cdms: list[dict]


# ── Status ─────────────────────────────────────────────────────────────────
class ConstellationStatus(BaseModel):
    satellite_count: int
    debris_count: int
    active_cdm_count: int
    health_score: float
    sim_time: datetime
    avg_fuel_pct: float
    nominal_count: int
