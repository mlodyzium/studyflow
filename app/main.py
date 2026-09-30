from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from alembic.script import ScriptDirectory
from alembic.config import Config
from app.core.config import settings
from app.core.traffic import snapshot
from app.db.database import SessionLocal
from app.core.logging import configure_logging
from app.core.middleware import log_requests
from app.core.i18n import localize_request
from app.routers import ai, auth, exam_results, exports, plans, study_sessions, subjects, tasks, topics, users

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
app.middleware("http")(localize_request)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(subjects.router)
app.include_router(topics.router)
app.include_router(tasks.router)
app.include_router(study_sessions.router)
app.include_router(exam_results.router)
app.include_router(ai.router)
app.include_router(plans.router)
app.include_router(exports.router)

@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["system"])
def ready_check() -> dict[str, str | bool]:
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
        current = db.scalar(text("SELECT version_num FROM alembic_version"))
    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    if current != head:
        raise HTTPException(status_code=503, detail="Database migration is pending")
    return {"status": "ready", "database": True, "migrations_current": True, "ai_configured": bool(settings.gemini_api_key)}


@app.get("/internal/metrics", tags=["system"])
def metrics(authorization: str | None = Header(default=None)) -> dict[str, int]:
    if not settings.metrics_token or authorization != f"Bearer {settings.metrics_token}":
        raise HTTPException(status_code=404, detail="Not found")
    result = snapshot()
    with SessionLocal() as db:
        result["users_total"] = db.scalar(text("SELECT count(*) FROM users")) or 0
        result["users_active_30d"] = db.scalar(text("SELECT count(DISTINCT user_uid) FROM study_sessions WHERE started_at >= now() - interval '30 days'")) or 0
    return result
