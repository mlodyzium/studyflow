from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app import models
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.study import UserRead, UserUpdate
from app.services import study

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserRead)
def me(user: models.User = Depends(get_current_user)):
    return user

@router.patch("/me", response_model=UserRead)
def update_me(payload: UserUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.update_user(db, user, payload)

@router.delete("/me", status_code=204)
def delete_me(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    study.delete_user(db, user); return Response(status_code=204)
