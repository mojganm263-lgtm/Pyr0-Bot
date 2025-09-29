# ---------- FILE: database.py ----------
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import datetime

# ---------- SQLite Database Setup ----------
DATABASE_URL = "sqlite:///bot_data.db"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ---------- Models ----------

class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(String, unique=True, nullable=False)
    lang1 = Column(String, nullable=False)
    lang2 = Column(String, nullable=False)
    flags = Column(String)  # store as JSON string

class Name(Base):
    __tablename__ = "names"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    kill_score = Column(Integer, default=0)
    vs_score = Column(Integer, default=0)
    history = relationship("ScoreHistory", back_populates="name")

class ScoreHistory(Base):
    __tablename__ = "score_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name_id = Column(Integer, ForeignKey("names.id"))
    category = Column(String)  # "kill" or "vs"
    value = Column(Integer)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    name = relationship("Name", back_populates="history")
