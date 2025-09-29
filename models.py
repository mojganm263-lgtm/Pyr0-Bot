# ---------- models.py ----------

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Score(Base):
    __tablename__ = "scores"
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True, nullable=False)
    category = Column(String, index=True, nullable=False)
    value = Column(Integer, nullable=False, default=0)

class History(Base):
    __tablename__ = "history"
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True, nullable=False)
    category = Column(String, index=True, nullable=False)
    value = Column(Integer, nullable=False)
    timestamp = Column(Integer, nullable=False)
