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