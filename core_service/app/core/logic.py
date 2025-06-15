import os
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session
from app.models.user_progress import UserProgress, LessonCompletion
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

VECTORSTORE_BASE_PATH = "app/static_data/vectorstores/"

def get_llm_local(model_name="gemini-2.0-flash-001", temperature=0.3, max_tokens=350):
    """
    Obtiene una instancia del modelo de lenguaje de Gemini.
    """
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=temperature,
        convert_system_message_to_human=True 
    )

def get_embeddings_local():
    """
    Obtiene una instancia de los embeddings de Google.
    """
    return GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=os.getenv("GOOGLE_API_KEY"))

def get_or_create_user_progress(db: Session, telegram_id: int, user_name: Optional[str] = None) -> tuple[UserProgress, int]:
    """
    Obtiene el progreso de un usuario o crea un nuevo registro.
    Ahora también actualiza el nombre del usuario.
    """
    today = date.today()
    user = db.query(UserProgress).filter(UserProgress.user_telegram_id == telegram_id).first()
    
    calculated_lesson_day = 1

    if user:
        # Actualiza el nombre si se proporciona uno nuevo
        if user_name and user.user_name != user_name:
            user.user_name = user_name
        
        days_since_start = (today - user.start_date).days
        calculated_lesson_day = max(1, days_since_start + 1)
        calculated_lesson_day = min(calculated_lesson_day, 30)
    else:
        # Crea el usuario con su nombre
        user = UserProgress(
            user_telegram_id=telegram_id,
            user_name=user_name,
            start_date=today,
            last_accessed_date=today
        )
        db.add(user)

    db.commit()
    db.refresh(user)
    return user, calculated_lesson_day


async def classify_user_intent(user_input: str) -> str:
    """
    Usa un LLM para clasificar la intención del usuario en una de cuatro categorías.
    """
    classifier_llm = get_llm_local(temperature=0, max_tokens=10)
    
    prompt = f"""
        Tu única tarea es clasificar el mensaje del usuario en una de estas 4 categorías: AFFIRMATIVE, NEGATIVE, QUESTION, GREETING.
        - AFFIRMATIVE: El usuario dice sí, está de acuerdo, o listo para continuar. Ejemplos: "si", "ok", "listo", "dale", "claro que si", "Siiiii".
        - NEGATIVE: El usuario dice no, pide esperar, o expresa duda. Ejemplos: "no", "espera un momento", "aún no".
        - QUESTION: El usuario está haciendo una pregunta o no entendió algo. Ejemplos: "¿qué es eso?", "no entiendo", "cómo hago para...".
        - GREETING: El usuario está saludando. Ejemplos: "hola", "buenos dias".

        Mensaje del usuario: "{user_input}"

        Responde únicamente con la palabra de la categoría. Categoría:
    """
    
    try:
        response = await classifier_llm.ainvoke(prompt)
        # Limpiamos la respuesta para obtener solo la categoría.
        return response.content.strip().upper()
    except Exception as e:
        print(f"Error en la clasificación de intención: {e}")
        return "UNKNOWN" # Devolver un estado desconocido en caso de error

async def validate_code_output(user_description: str, expected_output: str) -> bool:
    """
    Usa un LLM para verificar si la descripción del usuario confirma la salida esperada.
    """
    validator_llm = get_llm_local(temperature=0, max_tokens=10)
    
    prompt = f"""
        Tu única tarea es validar si la descripción del estudiante confirma que obtuvo el resultado correcto.
        El resultado esperado del código es: "{expected_output}"
        
        La descripción del estudiante de lo que vio en pantalla es: "{user_description}"

        ¿La descripción del estudiante confirma que vio el resultado esperado? El estudiante puede usar palabras extra o mostrar emoción.
        Responde únicamente con "true" o "false".
    """
    
    try:
        response = await validator_llm.ainvoke(prompt)
        # La respuesta del LLM será 'true' o 'false' en texto.
        return "true" in response.content.lower()
    except Exception as e:
        print(f"Error en la validación de la salida: {e}")
        return False
    
async def grade_quiz_answer(question: str, user_answer: str) -> bool:
    """
    Usa un LLM para calificar si la respuesta de un usuario es conceptualmente correcta.
    """
    evaluator_llm = get_llm_local(temperature=0, max_tokens=10)
    
    prompt = f"""
        Eres un evaluador experto de quizzes de programación. Tu tarea es calificar la respuesta del estudiante. Enfócate en el concepto, no en las palabras exactas.
        Pregunta del quiz:
        "{question}"
        Respuesta del estudiante:
        "{user_answer}"
        ¿Es la respuesta del estudiante conceptualmente correcta para la pregunta?
        Responde únicamente con "true" o "false".
    """
    
    try:
        response = await evaluator_llm.ainvoke(prompt)
        return "true" in response.content.lower()
    except Exception as e:
        print(f"Error en la calificación del quiz: {e}")
        return False
    
def load_daily_vectorstore(day_number: int) -> Optional[FAISS]:
    """
    Carga el índice FAISS para un día específico desde el disco.
    """
    day_store_path = os.path.join(VECTORSTORE_BASE_PATH, f"dia_{day_number}")
    index_file = os.path.join(day_store_path, "index.faiss")

    if not os.path.exists(index_file):
        print(f"Error: Vectorstore para el día {day_number} no encontrado en {day_store_path}")
        return None
    
    try:
        embeddings = get_embeddings_local()
        vectorstore = FAISS.load_local(day_store_path, embeddings, allow_dangerous_deserialization=True)
        print(f"Vectorstore para el día {day_number} cargado correctamente.")
        
        return vectorstore
    
    except Exception as e:
        print(f"Error crítico al cargar vectorstore para el día {day_number}: {e}")
        
        return None

def get_educational_rag_chain(vectorstore: FAISS, lesson_day: int):
    """
    Construye y devuelve una cadena de RAG con una personalidad de profe mejorada.
    """
    llm = get_llm_local(temperature=0.4)
    retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 5, "fetch_k": 20})

    personality = (
        "Eres 'PySis', una profesora de programación de Python apasionada y paciente. "
        "Tu misión es guiar a una estudiante en sus primeros pasos."
    )

    template_str = f"""{personality}

    **Tus Principios Pedagógicos:**
    1.  **Sé proactiva:** Si la pregunta del estudiante es una instrucción interna (ej. "INICIAR_LECCION", "INICIAR_TEMA_VARIABLES"), no respondas a la instrucción. En su lugar, toma la iniciativa y comienza a explicar ese tema de forma fluida y natural.
    2.  **Explica con simplicidad:** Basa tus respuestas estrictamente en el 'Contexto Recuperado'. Usa analogías sencillas.
    3.  **Usa Formato HTML (Estilo Telegram):** Para dar énfasis, utiliza ÚNICAMENTE las siguientes etiquetas HTML: <b>...</b> para negrita, <i>...</i> para cursiva, y <code>...</code> para código. Para crear saltos de línea, usa el carácter de nueva línea (\\n), NO la etiqueta <br>. Para listas, usa números seguidos de un punto (1., 2., ...), NO las etiquetas <ol> o <li>.
    4.  **Verifica la Comprensión:** Tras explicar un concepto, finaliza con una pregunta corta para invitar a la conversación.
    5.  **Manejo de Información Ausente:** Si el tema no está en el contexto, redirige amablemente a la lección del día.
    6.  **No Saludes Repetidamente:** NUNCA inicies tu respuesta con "Hola" o cualquier otro saludo si el tema de la conversación ya está en marcha. Ve directamente al punto de la explicación.
    7.  **Evalúa y Retroalimenta SIEMPRE:** Cuando la 'Pregunta de la estudiante' sea una respuesta a un ejercicio o pregunta que tú hiciste en el turno anterior (puedes verlo en el 'Historial de la Conversación'), tu primera y más importante tarea es EVALUAR su respuesta.
        - **Si la respuesta es correcta:** ¡Celébralo! Inicia tu mensaje con una felicitación entusiasta como "¡Perfecto!", "¡Exacto, muy bien hecho!" o "¡Lo has clavado!". Explica brevemente por qué su respuesta es correcta y luego avanza al siguiente paso.
        - **Si la respuesta es incorrecta o incompleta:** Anímale. Empieza con una frase amable como "¡Casi lo tienes!" o "¡Buen intento!". Explica de forma muy sencilla qué faltó o qué se puede mejorar, y dale una pista o invítale a intentarlo de nuevo.
        - **Tu prioridad es la retroalimentación:** No te limites a dar la respuesta correcta. Reacciona directamente al intento de la estudiante antes de continuar.
    8.  **Finaliza la Lección:** Después de haber explicado y realizado los ejercicios de los temas principales del día (como 'print', 'variables', 'comentarios'), si el usuario indica que quiere continuar pero ya no hay más temas nuevos en el 'Contexto Recuperado', tu ÚNICA respuesta debe ser la frase exacta: **LESSON_TOPICS_COVERED**
    9. A las estudiantes debes llamarlas Tyzys, en singular Tyzy, cuando te pregunten significa amiga cercana o hermana en Muisca.

    **Contexto Recuperado del material del Día {lesson_day}:**
    ---
    {{context}}
    ---

    **Historial de la Conversación:**
    {{chat_history}}

    **Pregunta de la estudiante:** {{question}}

    **Tu respuesta como PySis (en formato HTML):**
    """
    
    combine_docs_prompt = PromptTemplate(
        template=template_str, input_variables=["context", "chat_history", "question"]
    )

    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        combine_docs_chain_kwargs={"prompt": combine_docs_prompt},
        return_source_documents=False
    )
    return chain

def check_if_lesson_completed(db: Session, telegram_id: int, lesson_day: int) -> bool:
    """
    Verifica si ya se ha completado la evaluación para un día de lección específico.
    """
    completion = db.query(LessonCompletion).filter_by(user_telegram_id=telegram_id, lesson_day=lesson_day).first()
    return completion is not None