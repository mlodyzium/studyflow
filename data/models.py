"""Compatibility layer; new code should import from app.models."""
from app.models import ExamResult, Priority, StudySession, Subject, Task, Topic, User

__all__ = ["ExamResult", "Priority", "StudySession", "Subject", "Task", "Topic", "User"]
