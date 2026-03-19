"""
Booking Microservice — Database Configuration

Uses the same Base and engine as the auth service since both
services share the same PostgreSQL database.
"""
from app.auth.database import Base, engine, SessionLocal, get_db

# Re-export so Booking modules can import from here
__all__ = ["Base", "engine", "SessionLocal", "get_db"]