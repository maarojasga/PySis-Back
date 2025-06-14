from fastapi import FastAPI
from app.core.database import init_db
from app.routes import conversation

app = FastAPI(
    title="Core PySis RAG Service",
    description="Maneja la lógica del curso, progreso de usuarios y RAG diario."
)

@app.on_event("startup")
def on_startup():
    print("Iniciando Core Service (RAG Service)...")
    init_db()
    print("Core Service iniciado y base de datos lista.")

app.include_router(conversation.router, prefix="/conversation", tags=["Conversation"])

@app.get("/", tags=["Health Check"])
def read_root():
    return {"status": "Core Service (RAG Service) está funcionando"}