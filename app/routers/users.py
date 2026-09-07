from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.study import UserCreate, UserRead, UserUpdate
from app.services import study

router = APIRouter(prefix="/users", tags=["users"])

@router.post("", response_model=UserRead, status_code=201)
def create(payload: UserCreate, db: Session = Depends(get_db)):
    return study.create_user(db, payload)

@router.get("", response_model=list[UserRead])
def list_all(db: Session = Depends(get_db)):
    return study.list_users(db)

@router.get("/{user_uid}", response_model=UserRead)
def get_one(user_uid: UUID, db: Session = Depends(get_db)):
    return study.get_user(db, user_uid)

@router.patch("/{user_uid}", response_model=UserRead)
def update(user_uid: UUID, payload: UserUpdate, db: Session = Depends(get_db)):
    return study.update_user(db, user_uid, payload)

@router.delete("/{user_uid}", status_code=204)
def delete(user_uid: UUID, db: Session = Depends(get_db)):
    study.delete_user(db, user_uid)
    return Response(status_code=204)
