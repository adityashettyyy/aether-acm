"""
Database engine, session factory, and table initialization.
Uses SQLite for zero-configuration portability inside Docker.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DB_PATH = os.environ.get("DB_PATH", "/app/aether.db")
DATABASE_URL = "sqlite:///./aether.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db():
    """Create all tables if they don't exist."""
    from app.models import Satellite, Debris, ManeuverCommand, CDM, EventLog, GroundStation  # noqa: F401
    Base.metadata.create_all(bind=engine)
    print("[DB] Tables initialized.")


def get_db():
    """FastAPI dependency for DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
