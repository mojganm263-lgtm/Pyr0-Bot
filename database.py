# ---------- database.py — PART 2: database setup ----------
# Handles SQLAlchemy engine, session factory, and initialization

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Base class for models
Base = declarative_base()

# Database URL (default: SQLite file database.db in current folder)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database.db")

# Create engine (check_same_thread=False needed for SQLite + multithreading)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize the database and create tables if missing"""
    # Import models here to register them with Base before create_all
    import models
    Base.metadata.create_all(bind=engine)
