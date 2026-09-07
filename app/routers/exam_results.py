from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from app import models
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.pagination import Page
from app.schemas.study import ExamResultCreate, ExamResultRead, ExamResultUpdate
from app.services import study

router = APIRouter(prefix="/exam-results", tags=["exam results"])

@router.post("", response_model=ExamResultRead, status_code=201)
def create(payload: ExamResultCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.create_exam_result(db, payload, user.user_uid)

@router.get("", response_model=Page[ExamResultRead])
def list_all(subject_uid: UUID | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.list_exam_results(db, user.user_uid, subject_uid, page, page_size)

@router.get("/{uid}", response_model=ExamResultRead)
def get_one(uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.get_exam_result(db, uid, user.user_uid)

@router.patch("/{uid}", response_model=ExamResultRead)
def update(uid: UUID, payload: ExamResultUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.update_exam_result(db, uid, user.user_uid, payload)

@router.delete("/{uid}", status_code=204)
def delete(uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    study.delete_exam_result(db, uid, user.user_uid); return Response(status_code=204)
