from fastapi import FastAPI
from app.routes import stats

app = FastAPI(
    title="Statistics Service",
    description="Provee estadísticas sobre el progreso de las estudiantes en el curso."
)

app.include_router(stats.router, prefix="/stats", tags=["Statistics"])

@app.get("/", tags=["Health Check"])
def read_root():
    return {"status": "Statistics Service está funcionando"}