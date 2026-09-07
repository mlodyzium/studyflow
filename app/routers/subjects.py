from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.study import SubjectCreate, SubjectRead, SubjectUpdate
from app.services import study

router = APIRouter(prefix="/subjects", tags=["subjects"])

@router.post("", response_model=SubjectRead, status_code=201)
def create(payload: SubjectCreate, db: Session = Depends(get_db)):
    return study.create_subject(db, payload)

@router.get("", response_model=list[SubjectRead])
def list_all(user_uid: UUID | None = None, db: Session = Depends(get_db)):
    return study.list_subjects(db, user_uid)

@router.get("/{subject_uid}", response_model=SubjectRead)
def get_one(subject_uid: UUID, db: Session = Depends(get_db)):
    return study.get_subject(db, subject_uid)

@router.patch("/{subject_uid}", response_model=SubjectRead)
def update(subject_uid: UUID, payload: SubjectUpdate, db: Session = Depends(get_db)):
    return study.update_subject(db, subject_uid, payload)

@router.delete("/{subject_uid}", status_code=204)
def delete(subject_uid: UUID, db: Session = Depends(get_db)):
    study.delete_subject(db, subject_uid)
    return Response(status_code=204)
