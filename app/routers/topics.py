from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.study import TopicCreate, TopicRead, TopicUpdate
from app.services import study

router = APIRouter(prefix="/topics", tags=["topics"])

@router.post("", response_model=TopicRead, status_code=201)
def create(payload: TopicCreate, db: Session = Depends(get_db)):
    return study.create_topic(db, payload)

@router.get("", response_model=list[TopicRead])
def list_all(subject_uid: UUID | None = None, db: Session = Depends(get_db)):
    return study.list_topics(db, subject_uid)

@router.get("/{topic_uid}", response_model=TopicRead)
def get_one(topic_uid: UUID, db: Session = Depends(get_db)):
    return study.get_topic(db, topic_uid)

@router.patch("/{topic_uid}", response_model=TopicRead)
def update(topic_uid: UUID, payload: TopicUpdate, db: Session = Depends(get_db)):
    return study.update_topic(db, topic_uid, payload)

@router.delete("/{topic_uid}", status_code=204)
def delete(topic_uid: UUID, db: Session = Depends(get_db)):
    study.delete_topic(db, topic_uid)
    return Response(status_code=204)
