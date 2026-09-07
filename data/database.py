"""Compatibility layer; new code should import from app.db.database."""
from app.db.database import Base, SessionLocal, engine, get_db

__all__ = ["Base", "SessionLocal", "engine", "get_db"]
