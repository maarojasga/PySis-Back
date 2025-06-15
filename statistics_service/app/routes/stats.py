from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List
from app.database import get_db
from app.models import UserProgress
from app.schemas import StudentStat

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