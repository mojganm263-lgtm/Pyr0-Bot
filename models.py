# ---------- models.py — PART 3: database models ----------
# Defines the SQLAlchemy models for scores, history, and channels

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
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

    __table_args__ = (
        Index("idx_scores_name_category", "name", "category"),
        Index("idx_scores_timestamp", "timestamp"),
    )

class History(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, index=True)
    score_id = Column(Integer, ForeignKey("scores.id", ondelete="CASCADE"))
    old_value = Column(Float, nullable=False)
    new_value = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    score = relationship("Score", back_populates="history")

    __table_args__ = (
        Index("idx_history_score_id", "score_id"),
        Index("idx_history_timestamp", "timestamp"),
    )

class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String, index=True, nullable=False)
    channel_id = Column(String, index=True, nullable=False)

    __table_args__ = (
        Index("idx_channels_guild_id", "guild_id"),
    )
