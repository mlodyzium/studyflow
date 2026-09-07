from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from app import models
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.pagination import Page
from app.schemas.study import SubjectCreate, SubjectRead, SubjectUpdate
from app.services import study

router = APIRouter(prefix="/subjects", tags=["subjects"])

@router.post("", response_model=SubjectRead, status_code=201)
def create(payload: SubjectCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.create_subject(db, payload, user.user_uid)

@router.get("", response_model=Page[SubjectRead])
def list_all(search: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.list_subjects(db, user.user_uid, page, page_size, search)

@router.get("/{uid}", response_model=SubjectRead)
def get_one(uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.get_subject(db, uid, user.user_uid)

@router.patch("/{uid}", response_model=SubjectRead)
def update(uid: UUID, payload: SubjectUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.update_subject(db, uid, user.user_uid, payload)

@router.delete("/{uid}", status_code=204)
def delete(uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    study.delete_subject(db, uid, user.user_uid); return Response(status_code=204)
