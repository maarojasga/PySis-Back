from sqlalchemy import Column, BigInteger, String, Date, DateTime, Float, ForeignKey, UniqueConstraint, JSON, func
from sqlalchemy.orm import relationship
from datetime import datetime, date
from app.core.database import Base

class UserProgress(Base):
    __tablename__ = "user_progress"

    user_telegram_id = Column(BigInteger, primary_key=True, index=True)
    user_name = Column(String, nullable=True)
    start_date = Column(Date, nullable=False, default=date.today)
    last_accessed_date = Column(Date, nullable=False, default=date.today)
    completed_lessons = relationship("LessonCompletion", back_populates="user")
    session = relationship("UserSession", uselist=False, back_populates="user", cascade="all, delete-orphan")

class LessonCompletion(Base):
    __tablename__ = "lesson_completions"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_telegram_id = Column(BigInteger, ForeignKey("user_progress.user_telegram_id"), nullable=False)
    lesson_day = Column(BigInteger, nullable=False)
    completed_at = Column(DateTime, default=datetime.utcnow)
    evaluation_score = Column(Float, nullable=True)
    user = relationship("UserProgress", back_populates="completed_lessons")
    __table_args__ = (UniqueConstraint('user_telegram_id', 'lesson_day', name='uq_user_lesson_day'),)

class UserSession(Base):
    __tablename__ = "user_sessions"

    user_telegram_id = Column(BigInteger, ForeignKey("user_progress.user_telegram_id"), primary_key=True)
    session_data = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("UserProgress", back_populates="session")