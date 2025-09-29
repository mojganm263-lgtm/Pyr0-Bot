# ---------- database.py: SQLAlchemy engine & session factory ----------
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
    import models  # Import models to register them with Base
    Base.metadata.create_all(bind=engine)
