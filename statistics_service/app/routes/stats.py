from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, distinct
from typing import List
from datetime import date, timedelta
from app.database import get_db
from app.models import UserProgress, LessonCompletion
from app.schemas import StudentStat, DailyActivityStat, LessonPerformanceStat, ActiveUsersStat

router = APIRouter()

@router.get("/students", response_model=List[StudentStat])
def get_student_stats(db: Session = Depends(get_db)):
    """
    Obtiene una lista de todas las estudiantes y sus estadísticas de lecciones completadas.
    """
    students = db.query(UserProgress).options(
        joinedload(UserProgress.completed_lessons)
    ).all()
    return students

@router.get("/daily-activity", response_model=List[DailyActivityStat])
def get_daily_activity(db: Session = Depends(get_db)):
    """
    Calcula el número de usuarias activas por día.
    Ideal para una gráfica de líneas que muestre la actividad a lo largo del tiempo.
    """
    activity_stats = db.query(
        UserProgress.last_accessed_date.label("date"),
        func.count(UserProgress.user_telegram_id).label("active_users")
    ).group_by(UserProgress.last_accessed_date).order_by(UserProgress.last_accessed_date).all()
    return activity_stats

@router.get("/lesson-performance", response_model=List[LessonPerformanceStat])
def get_lesson_performance(db: Session = Depends(get_db)):
    """
    Calcula la puntuación promedio para cada lección completada.
    Útil para una gráfica de barras que compare la dificultad entre lecciones.
    """
    performance_stats = db.query(
        LessonCompletion.lesson_day.label("lesson_day"),
        func.avg(LessonCompletion.evaluation_score).label("average_score")
    ).group_by(LessonCompletion.lesson_day).order_by(LessonCompletion.lesson_day).all()
    return performance_stats

@router.get("/active-users-last-7-days", response_model=ActiveUsersStat)
def get_active_users_last_7_days(db: Session = Depends(get_db)):
    """
    Cuenta el número de usuarias únicas que se han conectado en los últimos 7 días.
    Perfecto para un "KPI card" en el dashboard.
    """
    seven_days_ago = date.today() - timedelta(days=7)

    count = db.query(
        func.count(distinct(UserProgress.user_telegram_id))
    ).filter(
        UserProgress.last_accessed_date >= seven_days_ago
    ).scalar()

    return {"active_users_count": count or 0}