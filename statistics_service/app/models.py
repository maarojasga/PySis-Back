from sqlalchemy import Column, BigInteger, String, Date, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import date, datetime
from .database import Base

class UserProgress(Base):
    __tablename__ = "user_progress"
    
    user_telegram_id = Column(BigInteger, primary_key=True, index=True)
    user_name = Column(String, nullable=True)
    start_date = Column(Date, nullable=False, default=date.today)
    last_accessed_date = Column(Date, nullable=False, default=date.today)
    completed_lessons = relationship("LessonCompletion", back_populates="user")

class LessonCompletion(Base):
    __tablename__ = "lesson_completions"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_telegram_id = Column(BigInteger, ForeignKey("user_progress.user_telegram_id"), nullable=False)
    lesson_day = Column(BigInteger, nullable=False)
    completed_at = Column(DateTime, default=datetime.utcnow)
    evaluation_score = Column(Float, nullable=True)
    user = relationship("UserProgress", back_populates="completed_lessons")