from sqlalchemy.orm import Session
from typing import Optional, Dict
from app.models.user_progress import LessonCompletion
from app.core import logic


DAILY_EVALUATIONS: Dict[int, list] = {
    1: [
        {"q": "¿Qué función de Python se usa para mostrar un mensaje en la pantalla?"},
        {"q": "Imagina que quieres guardar tu nombre en el programa. ¿Qué elemento de Python usarías?"},
        {"q": "¿Para qué sirve un comentario en el código, como los que empiezan con #?"},
    ]
}

async def start_evaluation_for_day(db: Session, telegram_id: int, lesson_day: int) -> tuple[str, Optional[dict]]:
    existing_completion = db.query(LessonCompletion).filter_by(user_telegram_id=telegram_id, lesson_day=lesson_day).first()
    if existing_completion:
        return f"¡Felicidades! Ya completaste la evaluación del Día {lesson_day}. Tu puntuación fue: {existing_completion.evaluation_score:.2f}%.", None

    if lesson_day not in DAILY_EVALUATIONS or not DAILY_EVALUATIONS[lesson_day]:
        return "No hay una evaluación disponible para este día.", None

    first_question = DAILY_EVALUATIONS[lesson_day][0]["q"]
    eval_state = {"current_q_index": 0, "answers": [], "lesson_day": lesson_day}
    
    return f"¡Es hora de la evaluación para el Día {lesson_day}!\n\n<b>Pregunta 1:</b> {first_question}", eval_state

async def process_evaluation_answer(db: Session, telegram_id: int, user_answer: str, eval_state: dict) -> tuple[str, Optional[dict]]:
    lesson_day = eval_state["lesson_day"]
    current_q_index = eval_state["current_q_index"]
    questions_for_day = DAILY_EVALUATIONS.get(lesson_day, [])
    eval_state["answers"].append(user_answer)
    next_q_index = current_q_index + 1
    
    if next_q_index < len(questions_for_day):
        eval_state["current_q_index"] = next_q_index
        next_question = questions_for_day[next_q_index]["q"]
        return f"¡Recibido! Siguiente pregunta (<b>Pregunta {next_q_index + 1}</b>):\n\n{next_question}", eval_state
    
    else:
        score = 0
        total_questions = len(questions_for_day)
        for i, q_data in enumerate(questions_for_day):
            question_text = q_data["q"]
            answer_text = eval_state["answers"][i]
            is_correct = await logic.grade_quiz_answer(
                question=question_text,
                user_answer=answer_text
            )
            
            if is_correct:
                score += 1
                
        final_score_percent = (score / total_questions) * 100 if total_questions > 0 else 0
        completion = LessonCompletion(
            user_telegram_id=telegram_id,
            lesson_day=lesson_day,
            evaluation_score=final_score_percent
        )
        db.add(completion)
        db.commit()

        return f"¡Evaluación del Día {lesson_day} completada! Tu puntuación final es: <b>{final_score_percent:.2f}%</b>. ¡Gran trabajo!", None