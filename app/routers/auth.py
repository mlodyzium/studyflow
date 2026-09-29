from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.study import LoginRequest, TokenRead, UserCreate, UserRead
from app.services import auth, study
from app.core.config import settings
from app.core.traffic import check_limit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    check_limit("register", request.client.host if request.client else "unknown", settings.registration_rate_limit_per_day, 86400)
    return study.create_user(db, payload)


@router.post("/login", response_model=TokenRead)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    check_limit("login", payload.username.casefold(), settings.login_rate_limit_per_15_min, 900)
    return TokenRead(access_token=auth.login(db, payload))
