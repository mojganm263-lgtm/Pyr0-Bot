from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    category = Column(String, index=True, nullable=False)
    value = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    history = relationship("History", back_populates="score", cascade="all, delete-orphan")

class History(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, index=True)
    score_id = Column(Integer, ForeignKey("scores.id"))
    old_value = Column(Float, nullable=False)
    new_value = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    score = relationship("Score", back_populates="history")

class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String, nullable=False)
    channel_id = Column(String, nullable=False)
