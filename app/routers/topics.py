from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from app import models
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.pagination import Page
from app.schemas.study import TopicCreate, TopicRead, TopicUpdate
from app.services import study

router = APIRouter(prefix="/topics", tags=["topics"])

@router.post("", response_model=TopicRead, status_code=201)
def create(payload: TopicCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.create_topic(db, payload, user.user_uid)

@router.get("", response_model=Page[TopicRead])
def list_all(subject_uid: UUID | None = None, difficulty: str | None = None, is_done: bool | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.list_topics(db, user.user_uid, subject_uid, page, page_size, difficulty, is_done)

@router.get("/{uid}", response_model=TopicRead)
def get_one(uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.get_topic(db, uid, user.user_uid)

@router.patch("/{uid}", response_model=TopicRead)
def update(uid: UUID, payload: TopicUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.update_topic(db, uid, user.user_uid, payload)

@router.delete("/{uid}", status_code=204)
def delete(uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    study.delete_topic(db, uid, user.user_uid); return Response(status_code=204)
