from datetime import datetime, timedelta, timezone
from math import ceil

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.schemas.study import LoginRequest
from app.core.traffic import count


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _locked_response(seconds: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail="Zbyt wiele błędnych haseł. Spróbuj ponownie później.",
        headers={"Retry-After": str(max(1, seconds))},
    )


def login(db: Session, data: LoginRequest) -> str:
    user = db.scalar(select(models.User).where(models.User.username == data.username).with_for_update())
    now = _now()
    if user is None:
        count("failed_login")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    locked_until = _as_utc(user.locked_until)
    if locked_until is not None and locked_until > now:
        count("login_locked")
        raise _locked_response(ceil((locked_until - now).total_seconds()))
    window_start = _as_utc(user.failed_login_window_started_at)
    if locked_until is not None or window_start is None or now - window_start >= timedelta(minutes=15):
        user.failed_login_attempts = 0
        user.failed_login_window_started_at = now
        user.locked_until = None
    if not verify_password(data.password, user.password_hash):
        user.failed_login_attempts += 1
        count("failed_login")
        if user.failed_login_attempts >= settings.failed_login_limit:
            user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
            db.commit()
            count("login_lock_started")
            raise _locked_response(settings.login_lock_minutes * 60)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid username or password")
    user.failed_login_attempts = 0
    user.failed_login_window_started_at = None
    user.locked_until = None
    db.commit()
    return create_access_token(user.user_uid)
