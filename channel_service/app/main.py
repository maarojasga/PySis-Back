from fastapi import FastAPI
from app.routes import telegram

app = FastAPI(
    title="Channel Service",
    description="Servicio para manejar la comunicación con canales externos como Telegram."
)

app.include_router(telegram.router)

@app.get("/", tags=["Health Check"])
def read_root():
    """
    Endpoint de verificación para saber si el servicio está funcionando.
    """
    return {"status": "Channel Service está funcionando"}