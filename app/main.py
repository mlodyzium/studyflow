from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import log_requests
from app.routers import ai, auth, exam_results, study_sessions, subjects, tasks, topics, users

configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(log_requests)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(subjects.router)
app.include_router(topics.router)
app.include_router(tasks.router)
app.include_router(study_sessions.router)
app.include_router(exam_results.router)
app.include_router(ai.router)

@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
