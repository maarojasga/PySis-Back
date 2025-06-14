from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas import QueryInput, ConversationResponse, ChatHistoryEntry
from app.core.database import get_db
from app.core import logic, evaluation
from typing import Dict

router = APIRouter()

active_evaluations_state: Dict[str, Dict] = {}

@router.post("/query", response_model=ConversationResponse)
async def handle_chat_query(query: QueryInput, db: Session = Depends(get_db)):
    """
    Punto de entrada principal para todas las interacciones del usuario.
    Orquesta la lógica para determinar si el usuario está en una evaluación o haciendo una pregunta RAG.
    """
    telegram_id_str = query.phone_number
    telegram_id_int = int(telegram_id_str)
    user_question = query.question.lower().strip()

    if telegram_id_str in active_evaluations_state:
        eval_state = active_evaluations_state[telegram_id_str]
        response_text, new_eval_state = await evaluation.process_evaluation_answer(
            db=db,
            telegram_id=telegram_id_int,
            user_answer=query.question,
            eval_state=eval_state
        )
        
        if new_eval_state:
            active_evaluations_state[telegram_id_str] = new_eval_state
        else:
            del active_evaluations_state[telegram_id_str]
            
        return ConversationResponse(
            conversation_id=telegram_id_str,
            answer=response_text,
            chat_history=[],
        )

    user_progress, lesson_day = logic.get_or_create_user_progress(db, telegram_id_int)
    
    if user_question in ["evaluacion", "evaluación", "examen", "prueba"]:
        response_text, eval_state = await evaluation.start_evaluation_for_day(db, telegram_id_int, lesson_day)
        
        if eval_state:
            active_evaluations_state[telegram_id_str] = eval_state
            
        return ConversationResponse(
            conversation_id=telegram_id_str,
            answer=response_text,
            chat_history=[],
        )

    vectorstore = logic.load_daily_vectorstore(lesson_day)
    if not vectorstore:
        raise HTTPException(status_code=500, detail=f"No se pudo cargar el material de estudio para el Día {lesson_day}.")
    
    rag_chain = logic.get_educational_rag_chain(vectorstore, lesson_day)
    
    chat_history = [] 
    
    try:
        result = rag_chain.invoke({
            "question": query.question,
            "chat_history": chat_history 
        })
        answer = result.get("answer", "No he podido encontrar una respuesta.")
    except Exception as e:
        print(f"Error durante la invocación de la cadena RAG: {e}")
        raise HTTPException(status_code=500, detail="Ocurrió un error al procesar tu pregunta.")

    return ConversationResponse(
        conversation_id=telegram_id_str,
        answer=answer,
        chat_history=[]
    )