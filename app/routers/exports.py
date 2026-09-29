from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.services import exports

router = APIRouter(tags=["exports"])


@router.get("/calendar/export.ics")
def export_calendar(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return Response(exports.calendar_ics(db, user), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="studyflow.ics"', "Cache-Control": "no-store"})


def _owned_note(db: Session, material_uid: UUID, user_uid: UUID):
    material = db.scalar(select(models.AiMaterial).where(models.AiMaterial.material_uid == material_uid,
                                                       models.AiMaterial.user_uid == user_uid,
                                                       models.AiMaterial.material_type == "notes"))
    if material is None: raise HTTPException(status_code=404, detail="Nie znaleziono notatki.")
    return material


@router.get("/ai/materials/{material_uid}/export.md")
def export_note_markdown(material_uid: UUID, db: Session = Depends(get_db),
                         user: models.User = Depends(get_current_user)):
    material = _owned_note(db, material_uid, user.user_uid)
    return Response(exports.notes_markdown(material), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="notatka-{material_uid}.md"', "Cache-Control": "no-store"})


@router.get("/ai/materials/{material_uid}/print")
def print_note(material_uid: UUID, db: Session = Depends(get_db),
               user: models.User = Depends(get_current_user)):
    material = _owned_note(db, material_uid, user.user_uid)
    return Response(exports.notes_print_html(material), media_type="text/html; charset=utf-8",
                    headers={"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'"})
