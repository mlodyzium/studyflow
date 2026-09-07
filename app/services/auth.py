from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.security import create_access_token, verify_password
from app.schemas.study import LoginRequest


def login(db: Session, data: LoginRequest) -> str:
    user = db.scalar(select(models.User).where(models.User.username == data.username))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return create_access_token(user.user_uid)
