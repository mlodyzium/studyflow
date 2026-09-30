from app.core.i18n import language, tr
from datetime import datetime, time, timedelta, timezone
from html import escape as html_escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.plans import study_instant


def _ics_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def _fold(line: str) -> str:
    pieces = []
    current = ""
    for char in line:
        if len((current + char).encode("utf-8")) > 75:
            pieces.append(current)
            current = " " + char
        else:
            current += char
    pieces.append(current)
    return "\r\n".join(pieces)


def calendar_ics(db: Session, user: models.User) -> bytes:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//StudyFlow//Study Calendar//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]

    def timed(uid: str, title: str, start: datetime, duration: int, description: str = ""):
        end = start + timedelta(minutes=max(duration, 15))
        lines.extend(("BEGIN:VEVENT", f"UID:{uid}@studyflow.local", f"DTSTAMP:{stamp}",
                      f"DTSTART:{start.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
                      f"DTEND:{end.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
                      f"SUMMARY:{_ics_text(title)}", f"DESCRIPTION:{_ics_text(description)}", "END:VEVENT"))

    tasks = db.scalars(select(models.Task).join(models.Topic).join(models.Subject).where(
        models.Subject.user_uid == user.user_uid, models.Task.is_done.is_(False))).all()
    linked_days = {day.calendar_task_uid: day for day in db.scalars(select(models.StudyPlanDay).join(models.StudyPlan).where(models.StudyPlan.user_uid == user.user_uid, models.StudyPlanDay.calendar_task_uid.is_not(None)))}
    for task in tasks:
        if task.deadline:
            timed(str(task.task_uid), task.title, task.deadline, linked_days[task.task_uid].duration_minutes if task.task_uid in linked_days else 45, task.notes or "")

    days = db.execute(select(models.StudyPlanDay, models.StudyPlan).join(models.StudyPlan).where(
        models.StudyPlan.user_uid == user.user_uid, models.StudyPlanDay.is_done.is_(False),
        (models.StudyPlanDay.calendar_task_uid.is_(None) | models.StudyPlanDay.scheduled_time.is_(None)))).all()
    for day, plan in days:
        description = f"{plan.title}\n{day.objective}\n" + "\n".join(day.activities)
        if day.scheduled_time:
            timed(str(day.day_uid), tr('Study: {0}', day.title), study_instant(day.scheduled_date, user, day.scheduled_time),
                  day.duration_minutes, description)
        else:
            end = day.scheduled_date + timedelta(days=1)
            lines.extend(("BEGIN:VEVENT", f"UID:{day.day_uid}@studyflow.local", f"DTSTAMP:{stamp}",
                          f"DTSTART;VALUE=DATE:{day.scheduled_date.strftime('%Y%m%d')}",
                          f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
                          f"SUMMARY:{_ics_text(tr('Study: {0}', day.title))}", f"DESCRIPTION:{_ics_text(description)}", "END:VEVENT"))

    subjects = db.scalars(select(models.Subject).where(models.Subject.user_uid == user.user_uid,
                                                       models.Subject.exam_date.is_not(None))).all()
    for subject in subjects:
        end = subject.exam_date + timedelta(days=1)
        lines.extend(("BEGIN:VEVENT", f"UID:exam-{subject.subject_uid}@studyflow.local", f"DTSTAMP:{stamp}",
                      f"DTSTART;VALUE=DATE:{subject.exam_date.strftime('%Y%m%d')}",
                      f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
                      f"SUMMARY:{_ics_text(tr('Exam: {0}', subject.name))}", "END:VEVENT"))
    lines.append("END:VCALENDAR")
    return ("\r\n".join(_fold(line) for line in lines) + "\r\n").encode("utf-8")


def notes_markdown(material: models.AiMaterial) -> str:
    data = material.content
    lines = [f"# {data.get('title', material.title)}", "", data.get("summary", ""), ""]
    for section in data.get("sections", []):
        lines.extend((f"## {section.get('heading', '')}", "", section.get("content", ""), ""))
    lines.extend((tr('## Key points'), ""))
    lines.extend(f"- {point}" for point in data.get("key_points", []))
    lines.extend(("", tr('## Test yourself'), ""))
    lines.extend(f"{number}. {question}" for number, question in enumerate(data.get("review_questions", []), 1))
    return "\n".join(lines).strip() + "\n"


def notes_print_html(material: models.AiMaterial) -> str:
    data = material.content
    sections = "".join(f"<section><h2>{html_escape(item.get('heading', ''))}</h2><p>{html_escape(item.get('content', '')).replace(chr(10), '<br>')}</p></section>" for item in data.get("sections", []))
    points = "".join(f"<li>{html_escape(item)}</li>" for item in data.get("key_points", []))
    questions = "".join(f"<li>{html_escape(item)}</li>" for item in data.get("review_questions", []))
    title = html_escape(data.get("title", material.title))
    return tr('<!doctype html><html lang="{6}"><meta charset="utf-8"><title>{0}</title>\n<style>body{font:16px/1.6 system-ui,sans-serif;max-width:800px;margin:40px auto;padding:0 20px;color:#19221b}h1{font-size:32px}h2{margin-top:32px}p{white-space:normal}button{padding:10px 16px}@media print{button{display:none}body{margin:0;max-width:none}}</style>\n<button onclick="window.print()">Save as PDF / Print</button><h1>{1}</h1><p>{2}</p>\n{3}<h2>Key points</h2><ul>{4}</ul><h2>Check yourself</h2><ol>{5}</ol></html>', title, title, html_escape(data.get('summary', '')), sections, points, questions, language.get())
