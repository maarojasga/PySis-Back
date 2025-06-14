from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from app.schemas import QueryInput, ConversationResponse
from app.core.database import get_db
from app.models.user_progress import UserSession
from app.core import logic, evaluation
from typing import Dict, Any
from datetime import date

router = APIRouter()

def get_or_create_session(db: Session, telegram_id_int: int) -> Dict[str, Any]:
    """Obtiene la sesión desde la BD o crea una nueva."""
    db_session = db.query(UserSession).filter(UserSession.user_telegram_id == telegram_id_int).first()
    if db_session:
        return db_session.session_data
    else:
        default_session_data = {"state": "START_DAY", "chat_history": [], "expected_output": None}
        new_db_session = UserSession(user_telegram_id=telegram_id_int, session_data=default_session_data)
        db.add(new_db_session)
        db.commit()
        db.refresh(new_db_session)
        return default_session_data

def save_session(db: Session, telegram_id_int: int, session_data: Dict[str, Any]):
    """Guarda la sesión actualizada en la BD."""
    db_session = db.query(UserSession).filter(UserSession.user_telegram_id == telegram_id_int).first()
    if db_session:
        db_session.session_data = session_data
        flag_modified(db_session, "session_data")
        db.commit()

@router.post("/query", response_model=ConversationResponse)
async def handle_chat_query(query: QueryInput, db: Session = Depends(get_db)):
    telegram_id_str = query.phone_number
    telegram_id_int = int(telegram_id_str)
    user_question = query.question
    user_name = query.user_name
    user_progress, lesson_day = logic.get_or_create_user_progress(
        db, telegram_id_int, user_name=user_name
    )
    session = get_or_create_session(db, telegram_id_int)
    
    if "chat_history" in session and isinstance(session["chat_history"], list):
        session["chat_history"] = [tuple(item) for item in session["chat_history"]]

    if user_progress.last_accessed_date != date.today():
        session = {"state": "START_DAY", "chat_history": [], "expected_output": None}
        user_progress.last_accessed_date = date.today()
        db.commit()

    current_state = session.get("state", "START_DAY")
    answer = "Lo siento, algo no salió como esperaba. ¿Podemos intentar de nuevo?"

    if current_state == "START_DAY":
        answer = (f"¡Hola! ¡Qué bueno verte! 🙌\n\nBienvenida a la <b>Lección del Día {lesson_day}</b>. "
                  f"¿Lista para empezar con la aventura de hoy?")
        session["state"] = "AWAITING_START_CONFIRMATION"

    elif current_state == "AWAITING_START_CONFIRMATION":
        intent = await logic.classify_user_intent(user_question)
        if intent == "AFFIRMATIVE":
            answer = ("¡Perfecto! Empecemos preparando tu espacio de trabajo en <b>Google Colab</b>.\n\n"
                      "1. Abre tu navegador y ve a <b>colab.research.google.com</b>.\n"
                      "2. En el menú, haz clic en <b>'Archivo' → 'Nuevo cuaderno'</b>.\n\n"
                      "Avísame con un 'listo' o similar cuando lo hayas creado.")
            session["state"] = "AWAITING_COLAB_READY"
        else:
            answer = "Sin problema. Cuando quieras empezar, solo dímelo."

    elif current_state == "AWAITING_COLAB_READY":
        intent = await logic.classify_user_intent(user_question)
        if intent == "AFFIRMATIVE":
            answer = ("¡Genial! Ahora, tu primer programa.\n\n"
                      "Escribe en Colab <b>exactamente</b> esto y ejecútalo:\n\n"
                      "<code>print(\"¡Hola, Mundo!\")</code>\n\n"
                      "Dime qué resultado te apareció en la pantalla.")
            session["state"] = "AWAITING_CODE_OUTPUT"
            session["expected_output"] = "¡Hola, Mundo!"
        else:
            answer = "No hay prisa. Avísame cuando estés lista para continuar."

    elif current_state == "AWAITING_CODE_OUTPUT":
        is_correct = await logic.validate_code_output(user_question, session["expected_output"])
        if is_correct:
            answer = ("¡Exacto! ¡Felicidades, primer programa completado!\n\n"
                      "Ahora que rompiste el hielo, ¿lista para aprender sobre las <b>variables</b>?")
            session["state"] = "PROMPT_FOR_VARIABLES"
        else:
            answer = (f"Mmm, no es correcto. El resultado debería ser <code>{session['expected_output']}</code>.\n\n"
                      "Revisa bien el código, ¡y dime qué obtienes!")

    elif current_state == "PROMPT_FOR_VARIABLES":
        intent = await logic.classify_user_intent(user_question)
        if intent == "AFFIRMATIVE" or intent == "QUESTION":
            session["state"] = "LESSON_Q&A"
            teacher_prompt = "INICIAR_TEMA_VARIABLES"
            vectorstore = logic.load_daily_vectorstore(lesson_day)
            rag_chain = logic.get_educational_rag_chain(vectorstore, lesson_day)
            result = await rag_chain.ainvoke({"question": teacher_prompt, "chat_history": session["chat_history"]})
            answer = result.get("answer")
            session["chat_history"].append((user_question, answer))
        else:
            answer = "Ok, tómate tu tiempo. Avísame cuando estés lista."

    elif current_state == "LESSON_Q&A":
        if user_question.lower().strip() in ["evaluacion", "evaluación", "examen", "test"]:
            response_text, eval_state = await evaluation.start_evaluation_for_day(db, telegram_id_int, lesson_day)
            if eval_state:
                session["state"] = "IN_EVALUATION"
                session["evaluation_state"] = eval_state
            answer = response_text
        else:
            vectorstore = logic.load_daily_vectorstore(lesson_day)
            rag_chain = logic.get_educational_rag_chain(vectorstore, lesson_day)
            result = await rag_chain.ainvoke({"question": user_question, "chat_history": session["chat_history"]})
            rag_answer = result.get("answer", "")
            
            if "LESSON_TOPICS_COVERED" in rag_answer:
                session["state"] = "PROMPT_FOR_EVALUATION"
                answer = "¡Excelente trabajo! Parece que hemos cubierto todos los temas de hoy. Para asegurarnos de que todo quedó claro, ¿te gustaría hacer una pequeña prueba de 3 preguntas?"
            else:
                answer = rag_answer
                session["chat_history"].append((user_question, answer))

    elif current_state == "PROMPT_FOR_EVALUATION":
        intent = await logic.classify_user_intent(user_question)
        if intent == "AFFIRMATIVE":
            response_text, eval_state = await evaluation.start_evaluation_for_day(db, telegram_id_int, lesson_day)
            if eval_state:
                session["state"] = "IN_EVALUATION"
                session["evaluation_state"] = eval_state
            answer = response_text
        else:
            session["state"] = "DAY_COMPLETE"
            answer = "¡No hay problema! Puedes tomar la evaluación cuando quieras escribiendo 'evaluación'. Si no, ¡nos vemos mañana para la siguiente lección! 🚀"

    elif current_state == "IN_EVALUATION":
        eval_state = session.get("evaluation_state", {})
        response_text, new_eval_state = await evaluation.process_evaluation_answer(db, telegram_id_int, user_question, eval_state)
        answer = response_text
        if new_eval_state:
            session["evaluation_state"] = new_eval_state
        else:
            session["state"] = "DAY_COMPLETE"
            session.pop("evaluation_state", None)
            answer += "\n\n¡Lección del día completada! 💪 Si tienes más dudas sobre este tema, puedes seguir preguntando. Si no, ¡nos vemos mañana para la siguiente lección! 🚀"

    elif current_state == "DAY_COMPLETE":
        answer = "¡Lección del día completada! 💪 Si tienes más dudas sobre este tema, puedes seguir preguntando. Si no, ¡nos vemos mañana para la siguiente lección! 🚀"

    save_session(db, telegram_id_int, session)
    return ConversationResponse(
        conversation_id=telegram_id_str, answer=answer
    )