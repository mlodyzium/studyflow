from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from app import models
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.pagination import Page
from app.schemas.study import StudySessionCreate, StudySessionRead, StudySessionUpdate
from app.services import study

router = APIRouter(prefix="/study-sessions", tags=["study sessions"])

@router.post("", response_model=StudySessionRead, status_code=201)
def create(payload: StudySessionCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.create_study_session(db, payload, user.user_uid)

@router.get("", response_model=Page[StudySessionRead])
def list_all(subject_uid: UUID | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.list_study_sessions(db, user.user_uid, subject_uid, page, page_size)

@router.get("/{uid}", response_model=StudySessionRead)
def get_one(uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.get_study_session(db, uid, user.user_uid)

@router.patch("/{uid}", response_model=StudySessionRead)
def update(uid: UUID, payload: StudySessionUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.update_study_session(db, uid, user.user_uid, payload)

@router.delete("/{uid}", status_code=204)
def delete(uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    study.delete_study_session(db, uid, user.user_uid); return Response(status_code=204)
