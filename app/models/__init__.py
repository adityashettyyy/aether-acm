"""ORM models — all in one file for simplicity."""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Boolean, DateTime, Integer, Text, ForeignKey
from app.db.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Satellite(Base):
    __tablename__ = "satellites"
    id         = Column(String, primary_key=True)
    mass_kg    = Column(Float, default=550.0)
    fuel_kg    = Column(Float, default=50.0)
    pos_x      = Column(Float)
    pos_y      = Column(Float)
    pos_z      = Column(Float)
    vel_x      = Column(Float)
    vel_y      = Column(Float)
    vel_z      = Column(Float)
    slot_x     = Column(Float)
    slot_y     = Column(Float)
    slot_z     = Column(Float)
    status     = Column(String, default="NOMINAL")
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class Debris(Base):
    __tablename__ = "debris"
    id         = Column(String, primary_key=True)
    pos_x      = Column(Float)
    pos_y      = Column(Float)
    pos_z      = Column(Float)
    vel_x      = Column(Float)
    vel_y      = Column(Float)
    vel_z      = Column(Float)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class ManeuverCommand(Base):
    __tablename__ = "maneuvers"
    id               = Column(String, primary_key=True)
    satellite_id     = Column(String, ForeignKey("satellites.id"))
    burn_id          = Column(String)
    burn_time        = Column(DateTime)
    dv_x             = Column(Float)
    dv_y             = Column(Float)
    dv_z             = Column(Float)
    fuel_consumed_kg = Column(Float, default=0.0)
    status           = Column(String, default="PENDING")
    created_at       = Column(DateTime, default=utcnow)


class CDM(Base):
    __tablename__ = "cdm"
    id           = Column(String, primary_key=True)
    satellite_id = Column(String)
    debris_id    = Column(String)
    tca          = Column(DateTime)
    miss_dist_km = Column(Float)
    risk_level   = Column(String)
    resolved     = Column(Boolean, default=False)
    created_at   = Column(DateTime, default=utcnow)


class EventLog(Base):
    __tablename__ = "event_log"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    satellite_id = Column(String)
    event_type   = Column(String)
    timestamp    = Column(DateTime, default=utcnow)
    metadata_    = Column("metadata", Text)


class GroundStation(Base):
    __tablename__ = "ground_stations"
    id          = Column(String, primary_key=True)
    name        = Column(String)
    lat         = Column(Float)
    lon         = Column(Float)
    elevation_m = Column(Float)
    min_el_deg  = Column(Float)
