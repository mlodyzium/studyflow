from fastapi import FastAPI
from app.core.config import settings
from app.routers import subjects, tasks, topics, users

app = FastAPI(title=settings.app_name, version="1.0.0")
app.include_router(users.router)
app.include_router(subjects.router)
app.include_router(topics.router)
app.include_router(tasks.router)

@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
