from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class LessonStat(BaseModel):
    lesson_day: int
    evaluation_score: Optional[float]

    class Config:
        orm_mode = True

class StudentStat(BaseModel):
    user_telegram_id: int
    user_name: Optional[str] = "Anónima"
    start_date: date
    last_accessed_date: date
    completed_lessons: List[LessonStat] = []

    class Config:
        orm_mode = True
        
class DailyActivityStat(BaseModel):
    """
    Schema for daily active user counts.
    """
    date: date
    active_users: int

    class Config:
        orm_mode = True

class LessonPerformanceStat(BaseModel):
    """
    Schema for the average score per lesson.
    """
    lesson_day: int
    average_score: Optional[float] = 0.0

    class Config:
        orm_mode = True

class ActiveUsersStat(BaseModel):
    """
    Schema para el conteo de usuarias activas en un periodo.
    """
    active_users_count: int