import getpass
from datetime import datetime

from data.auth import hash_password, verify_password
from data.database import SessionLocal
from data.models import ExamResult as ExamResultModel
from data.models import Priority, User
from data.models import StudySession as StudySessionModel
from data.models import Subject as SubjectModel
from data.models import Task as TaskModel
from data.models import Topic as TopicModel

DIFFICULTY_OPTIONS = ["EASY", "MEDIUM", "HARD"]
PRIORITY_OPTIONS = [p.value for p in Priority]


# ---------- Helpers for user input ----------

def ask_date(prompt, allow_empty=True):
    """Ask for a YYYY-MM-DD date, or return None when an empty value is allowed."""
    while True:
        info = ' (YYYY-MM-DD, press enter to skip)' if allow_empty else " (YYYY-MM-DD)"
        raw = input(f"{prompt}{info}: ").strip()
        if not raw and allow_empty:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()  # noqa: DTZ007
        except ValueError:
            print('Invalid date format! Use YYYY-MM-DD.')


def ask_int(prompt, allow_empty=True, min_value=None):
    while True:
        info = ' (press enter to skip)' if allow_empty else ""
        raw = input(f"{prompt}{info}: ").strip()
        if not raw and allow_empty:
            return None
        try:
            value = int(raw)
            if min_value is not None and value < min_value:
                print('Value must be >= {0}!'.format(min_value))
                continue
            return value
        except ValueError:
            print('Enter an integer!')


def ask_float(prompt, allow_empty=True, min_value=None, max_value=None):
    while True:
        info = ' (press enter to skip)' if allow_empty else ""
        raw = input(f"{prompt}{info}: ").strip()
        if not raw and allow_empty:
            return None
        try:
            value = float(raw)
            if min_value is not None and value < min_value:
                print('Value must be >= {0}!'.format(min_value))
                continue
            if max_value is not None and value > max_value:
                print('Value must be <= {0}!'.format(max_value))
                continue
            return value
        except ValueError:
            print('Enter a number!')


def ask_choice(prompt, options, allow_empty=True):
    while True:
        info = ' ({0}, press enter to skip)'.format('/'.join(options)) if allow_empty else f" ({'/'.join(options)})"
        raw = input(f"{prompt}{info}: ").strip().upper()
        if not raw and allow_empty:
            return None
        if raw in options:
            return raw
        print('Invalid option!')


# ---------- Logowanie / rejestracja ----------

class Auth:
    def register(self):
        session = SessionLocal()

        while True:
            username = input('Choose a username: ').strip().lower()
            if not username:
                print('Username cannot be empty!')
                continue

            existing = session.query(User).filter(User.username == username).first()
            if existing:
                print('This user already exists!')
                continue
            break

        while True:
            password = getpass.getpass('Choose a password: ')
            if len(password) < 4:
                print('Password must be at least 4 characters long!')
                continue

            if getpass.getpass('Repeat password: ') != password:
                print('Passwords do not match!')
                continue
            break

        new_user = User(username=username, password_hash=hash_password(password))
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        print('Registered successfully! Welcome, {0}.'.format(username))

        user_uid = new_user.user_uid
        session.close()
        return user_uid

    def login(self):
        session = SessionLocal()

        while True:
            username = input('Username: ').strip().lower()
            password = getpass.getpass('Password: ')

            user = session.query(User).filter(User.username == username).first()

            if not user or not verify_password(password, user.password_hash):
                print('Invalid username or password!')
                if input('Try again? (y/n): ').strip().lower() != 'y':
                    session.close()
                    return None
                continue

            print('Logged in successfully! Welcome, {0}.'.format(username))
            user_uid = user.user_uid
            session.close()
            return user_uid


# ---------- Przedmioty ----------

class SubjectService:
    def __init__(self, user_uid):
        self.user_uid = user_uid

    def _get_all(self, session):
        return (
            session.query(SubjectModel)
            .filter(SubjectModel.user_uid == self.user_uid)
            .order_by(SubjectModel.nazwa)
            .all()
        )

    def _select(self, session, prompt='Enter subject name'):
        subjects = self._get_all(session)
        if not subjects:
            print('No subjects!')
            return None

        for s in subjects:
            data = ' (exam: {0})'.format(s.exam_date) if s.exam_date else ""
            print(f"- {s.nazwa}{data}")

        while True:
            nazwa = input("\n{0} (or 'cancel'): ".format(prompt)).strip().lower()
            if nazwa == 'cancel':
                return None
            subject = next((s for s in subjects if s.nazwa == nazwa), None)
            if not subject:
                print('No subject found with that name!')
                continue
            return subject

    def add(self):
        session = SessionLocal()

        while True:
            nazwa = input('Enter subject name: ').strip().lower()
            if not nazwa:
                print('Name cannot be empty!')
                session.close()
                return

            if session.query(SubjectModel).filter(
                SubjectModel.user_uid == self.user_uid, SubjectModel.nazwa == nazwa
            ).first():
                print('This subject already exists!')
                continue
            break

        exam_date = ask_date('Exam date')

        new_subject = SubjectModel(nazwa=nazwa, user_uid=self.user_uid, exam_date=exam_date)
        session.add(new_subject)
        session.commit()
        print('Subject added!')
        session.close()

    def edit(self):
        session = SessionLocal()
        subject = self._select(session, 'Which subject do you want to edit?')
        if not subject:
            session.close()
            return

        nowa_nazwa = input("New name (press enter to keep '{0}'): ".format(subject.nazwa)).strip().lower()
        if nowa_nazwa:
            exists = session.query(SubjectModel).filter(
                SubjectModel.user_uid == self.user_uid, SubjectModel.nazwa == nowa_nazwa
            ).first()
            if exists:
                print('A subject with that name already exists! Cancelled.')
                session.close()
                return
            subject.nazwa = nowa_nazwa

        nowa_data = ask_date('New exam date')
        if nowa_data:
            subject.exam_date = nowa_data

        session.commit()
        print('Subject updated!')
        session.close()

    def delete(self):
        session = SessionLocal()
        subject = self._select(session, 'Which subject do you want to delete?')
        if not subject:
            session.close()
            return

        if input("Are you sure you want to delete '{0}' and everything it contains? (yes/no): ".format(subject.nazwa)).strip().lower() != 'yes':
            print('Cancelled.')
            session.close()
            return

        session.delete(subject)
        session.commit()
        print('Subject removed.')
        session.close()

    def show(self):
        session = SessionLocal()
        subjects = self._get_all(session)
        if not subjects:
            print('No subjects!')
        for s in subjects:
            data = ' (exam: {0})'.format(s.exam_date) if s.exam_date else ""
            print(f"- {s.nazwa}{data}")
        session.close()


# ---------- Tematy ----------

class TopicService:
    def __init__(self, user_uid):
        self.user_uid = user_uid
        self.subjects = SubjectService(user_uid)

    def _get_all(self, session, subject):
        return (
            session.query(TopicModel)
            .filter(TopicModel.subject_uid == subject.subject_uid)
            .order_by(TopicModel.nazwa)
            .all()
        )

    def _select(self, session, subject, prompt='Enter the topic name'):
        topics = self._get_all(session, subject)
        if not topics:
            print('No topics in this subject!')
            return None

        for t in topics:
            status = 'mastered' if t.status else 'in progress'
            trudnosc = ', difficulty: {0}'.format(t.difficulty) if t.difficulty else ""
            print(f"- {t.nazwa} ({status}{trudnosc})")

        while True:
            nazwa = input("\n{0} (or 'cancel'): ".format(prompt)).strip().lower()
            if nazwa == 'cancel':
                return None
            topic = next((t for t in topics if t.nazwa == nazwa), None)
            if not topic:
                print('No topic found with that name!')
                continue
            return topic

    def add(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'To which subject do you want to add the topic?')
        if not subject:
            session.close()
            return

        while True:
            nazwa = input('Enter the topic name: ').strip().lower()
            if not nazwa:
                print('Name cannot be empty!')
                session.close()
                return
            if session.query(TopicModel).filter(
                TopicModel.subject_uid == subject.subject_uid, TopicModel.nazwa == nazwa
            ).first():
                print('This topic already exists in this subject!')
                continue
            break

        difficulty = ask_choice('Difficulty level', DIFFICULTY_OPTIONS)

        new_topic = TopicModel(nazwa=nazwa, subject_uid=subject.subject_uid, difficulty=difficulty)
        session.add(new_topic)
        session.commit()
        print('Topic added!')
        session.close()

    def edit(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'In which subject are you editing the topic?')
        if not subject:
            session.close()
            return

        topic = self._select(session, subject, 'Which topic are you editing?')
        if not topic:
            session.close()
            return

        nowa_nazwa = input("New name (press enter to keep '{0}'): ".format(topic.nazwa)).strip().lower()
        if nowa_nazwa:
            topic.nazwa = nowa_nazwa

        nowa_trudnosc = ask_choice('New difficulty level', DIFFICULTY_OPTIONS)
        if nowa_trudnosc:
            topic.difficulty = nowa_trudnosc

        zmiana_statusu = input('Mark as mastered? (yes/no/enter to skip): ').strip().lower()
        if zmiana_statusu == 'yes':
            topic.status = True
        elif zmiana_statusu == 'no':
            topic.status = False

        session.commit()
        print('Topic updated!')
        session.close()

    def delete(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'In which subject do you want to delete the topic?')
        if not subject:
            session.close()
            return

        topic = self._select(session, subject, 'Which topic to delete?')
        if not topic:
            session.close()
            return

        if input("Are you sure you want to delete the topic '{0}' along with its tasks? (yes/no): ".format(topic.nazwa)).strip().lower() != 'yes':
            print('Cancelled.')
            session.close()
            return

        session.delete(topic)
        session.commit()
        print('Topic removed.')
        session.close()

    def show(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "Whose subject's topics should be shown?")
        if not subject:
            session.close()
            return

        topics = self._get_all(session, subject)
        if not topics:
            print('No topics.')
        for t in topics:
            status = 'mastered' if t.status else 'in progress'
            trudnosc = ', difficulty: {0}'.format(t.difficulty) if t.difficulty else ""
            print(f"- {t.nazwa} ({status}{trudnosc})")
        session.close()


# ---------- Zadania ----------

class TaskService:
    def __init__(self, user_uid):
        self.user_uid = user_uid
        self.subjects = SubjectService(user_uid)
        self.topics = TopicService(user_uid)

    def _get_all(self, session, topic):
        return (
            session.query(TaskModel)
            .filter(TaskModel.topic_uid == topic.topic_uid)
            .all()
        )

    def _title_exists(self, session, topic, title, exclude_task=None):
        normalized_title = title.strip().lower()
        return any(
            task is not exclude_task and task.title.strip().lower() == normalized_title
            for task in self._get_all(session, topic)
        )

    def _select_task(self, session, topic, prompt='Enter the task content'):
        tasks = self._get_all(session, topic)
        if not tasks:
            print('No tasks in this topic!')
            return None

        for t in tasks:
            status = 'Completed' if t.is_done else " "
            deadline = ', due date: {0}'.format(t.deadline.date()) if t.deadline else ""
            print('  [{0}] {1} (priority: {2}{3})'.format(status, t.title, t.priority.value, deadline))

        while True:
            tresc = input("\n{0} (or 'cancel'): ".format(prompt)).strip()
            if tresc.lower() == 'cancel':
                return None
            matches = [t for t in tasks if t.title.strip().lower() == tresc.lower()]
            if not matches:
                print('No task found with that content!')
                continue
            if len(matches) > 1:
                print('Several tasks have the same content — please rename one of them.')
                continue
            return matches[0]

    def _pick_topic(self, session, subject):
        """Select an existing topic or create a new one immediately."""
        topics = self.topics._get_all(session, subject)
        if topics:
            for t in topics:
                print(f"- {t.nazwa}")
            nazwa = input('\nEnter the topic name (existing or new): ').strip().lower()
        else:
            print("This subject has no topics yet — let's create the first one.")
            nazwa = input('Enter the new topic name: ').strip().lower()

        if not nazwa:
            print('Topic name cannot be empty!')
            return None

        topic = next((t for t in topics if t.nazwa == nazwa), None)
        if topic:
            return topic

        difficulty = ask_choice('Difficulty level of the new topic', DIFFICULTY_OPTIONS)
        new_topic = TopicModel(nazwa=nazwa, subject_uid=subject.subject_uid, difficulty=difficulty)
        session.add(new_topic)
        session.commit()
        session.refresh(new_topic)
        return new_topic

    def add(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'To which subject do you want to add the task?')
        if not subject:
            session.close()
            return

        topic = self._pick_topic(session, subject)
        if not topic:
            session.close()
            return

        while True:
            title = input('Enter the task content: ').strip()
            if not title:
                print('Content cannot be empty!')
                continue
            if self._title_exists(session, topic, title):
                print('A task with this content already exists in this topic!')
                continue
            break

        deadline_date = ask_date('Due date')
        deadline = datetime.combine(deadline_date, datetime.min.time()) if deadline_date else None
        priority = ask_choice('Priority', PRIORITY_OPTIONS) or Priority.MEDIUM.value

        new_task = TaskModel(title=title, topic_uid=topic.topic_uid, deadline=deadline, priority=priority)
        session.add(new_task)
        session.commit()
        print('Task added!')
        session.close()

    def edit(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'In which subject are you editing the task?')
        if not subject:
            session.close()
            return

        topic = self.topics._select(session, subject, 'In which topic?')
        if not topic:
            session.close()
            return

        task = self._select_task(session, topic, 'Which task are you editing?')
        if not task:
            session.close()
            return

        while True:
            nowa_tresc = input("New content (press enter to keep '{0}'): ".format(task.title)).strip()
            if not nowa_tresc or not self._title_exists(session, topic, nowa_tresc, task):
                break
            print('A task with this content already exists in this topic!')
        if nowa_tresc:
            task.title = nowa_tresc

        nowy_termin = ask_date('New deadline')
        if nowy_termin:
            task.deadline = datetime.combine(nowy_termin, datetime.min.time())

        nowy_priorytet = ask_choice('New priority', PRIORITY_OPTIONS)
        if nowy_priorytet:
            task.priority = nowy_priorytet

        session.commit()
        print('Task updated!')
        session.close()

    def delete(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'In which subject do you want to delete the task?')
        if not subject:
            session.close()
            return

        topic = self.topics._select(session, subject, 'In which topic?')
        if not topic:
            session.close()
            return

        task = self._select_task(session, topic, 'Which task do you want to delete?')
        if not task:
            session.close()
            return

        if input("Are you sure you want to delete '{0}'? (yes/no): ".format(task.title)).strip().lower() != 'yes':
            print('Cancelled.')
            session.close()
            return

        session.delete(task)
        session.commit()
        print('Task deleted.')
        session.close()

    def complete(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'In which subject?')
        if not subject:
            session.close()
            return

        topic = self.topics._select(session, subject, 'In which topic?')
        if not topic:
            session.close()
            return

        task = self._select_task(session, topic, 'Which task did you complete?')
        if not task:
            session.close()
            return

        if task.is_done:
            print('The task has already been completed!')
        else:
            task.is_done = True
            session.commit()
            print('Task status changed!')
        session.close()

    def show(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'Show tasks for which subject?')
        if not subject:
            session.close()
            return

        topics = self.topics._get_all(session, subject)
        if not topics:
            print('No topics (and therefore no tasks).')
            session.close()
            return

        for topic in topics:
            print('\nTopic: {0}'.format(topic.nazwa))
            tasks = self._get_all(session, topic)
            if not tasks:
                print('  (no tasks)')
            for t in tasks:
                status = 'Completed' if t.is_done else " "
                deadline = ', due date: {0}'.format(t.deadline.date()) if t.deadline else ""
                print('  [{0}] {1} (priority: {2}{3})'.format(status, t.title, t.priority.value, deadline))

        session.close()


# ---------- Sesje nauki ----------

class StudySessionService:
    def __init__(self, user_uid):
        self.user_uid = user_uid
        self.subjects = SubjectService(user_uid)

    def _get_all(self, session, subject):
        return (
            session.query(StudySessionModel)
            .filter(StudySessionModel.subject_uid == subject.subject_uid)
            .order_by(StudySessionModel.started_at.desc())
            .all()
        )

    def add(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'For which subject do you want to save the study session?')
        if not subject:
            session.close()
            return

        duration = ask_int('How many minutes did the session last?', allow_empty=False, min_value=1)
        notes = input('Notes (optional): ').strip() or None

        new_session = StudySessionModel(
            subject_uid=subject.subject_uid,
            duration_minutes=duration,
            notes=notes,
        )
        session.add(new_session)
        session.commit()
        print('Study session saved!')
        session.close()

    def show(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'Show sessions for which subject?')
        if not subject:
            session.close()
            return

        sessions = self._get_all(session, subject)
        if not sessions:
            print('No study sessions.')
        for s in sessions:
            notatka = f" — {s.notes}" if s.notes else ""
            print(f"- {s.started_at.strftime('%Y-%m-%d %H:%M')}, {s.duration_minutes} min{notatka}")
        session.close()

    def edit(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'In which subject are you editing the session?')
        if not subject:
            session.close()
            return

        sessions = self._get_all(session, subject)
        if not sessions:
            print('No study sessions.')
            session.close()
            return

        for i, s in enumerate(sessions, start=1):
            notatka = f" — {s.notes}" if s.notes else ""
            print(f"{i}. {s.started_at.strftime('%Y-%m-%d %H:%M')}, {s.duration_minutes} min{notatka}")

        numer = ask_int('Session number to edit', allow_empty=False, min_value=1)
        if numer is None or numer > len(sessions):
            print('Invalid number!')
            session.close()
            return

        target = sessions[numer - 1]
        nowy_czas = ask_int('New duration (minutes)', min_value=1)
        if nowy_czas is not None:
            target.duration_minutes = nowy_czas

        nowe_notatki = input('New notes (press enter to keep unchanged): ').strip()
        if nowe_notatki:
            target.notes = nowe_notatki

        session.commit()
        print('Session updated!')
        session.close()

    def delete(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'In which subject do you want to delete the session?')
        if not subject:
            session.close()
            return

        sessions = self._get_all(session, subject)
        if not sessions:
            print('No study sessions.')
            session.close()
            return

        for i, s in enumerate(sessions, start=1):
            print(f"{i}. {s.started_at.strftime('%Y-%m-%d %H:%M')}, {s.duration_minutes} min")

        numer = ask_int('Session number to delete', allow_empty=False, min_value=1)
        if numer is None or numer > len(sessions):
            print('Invalid number!')
            session.close()
            return

        target = sessions[numer - 1]
        if input('Are you sure you want to delete? (yes/no): ').strip().lower() != 'yes':
            print('Cancelled.')
            session.close()
            return

        session.delete(target)
        session.commit()
        print('Session deleted.')
        session.close()


# ---------- Exam results ----------

class ExamResultService:
    def __init__(self, user_uid):
        self.user_uid = user_uid
        self.subjects = SubjectService(user_uid)

    def _get_all(self, session, subject):
        return (
            session.query(ExamResultModel)
            .filter(ExamResultModel.subject_uid == subject.subject_uid)
            .order_by(ExamResultModel.exam_date.desc())
            .all()
        )

    def add(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'For which subject do you want to save the score?')
        if not subject:
            session.close()
            return

        exam_date = ask_date('Exam date', allow_empty=False)
        score = ask_float('Score in %', allow_empty=False, min_value=0, max_value=100)

        new_result = ExamResultModel(subject_uid=subject.subject_uid, exam_date=exam_date, score_percent=score)
        session.add(new_result)
        session.commit()
        print('Exam score saved!')
        session.close()

    def show(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'Show scores for which subject?')
        if not subject:
            session.close()
            return

        results = self._get_all(session, subject)
        if not results:
            print('No scores.')
        for r in results:
            print(f"- {r.exam_date}: {r.score_percent}%")
        session.close()

    def edit(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'In which subject are you editing the score?')
        if not subject:
            session.close()
            return

        results = self._get_all(session, subject)
        if not results:
            print('No scores.')
            session.close()
            return

        for i, r in enumerate(results, start=1):
            print(f"{i}. {r.exam_date}: {r.score_percent}%")

        numer = ask_int('Score number to edit', allow_empty=False, min_value=1)
        if numer is None or numer > len(results):
            print('Invalid number!')
            session.close()
            return

        target = results[numer - 1]
        nowa_data = ask_date('New exam date')
        if nowa_data:
            target.exam_date = nowa_data

        nowy_wynik = ask_float('New score in %', min_value=0, max_value=100)
        if nowy_wynik is not None:
            target.score_percent = nowy_wynik

        session.commit()
        print('Score updated!')
        session.close()

    def delete(self):
        session = SessionLocal()
        subject = self.subjects._select(session, 'In which subject do you want to delete the score?')
        if not subject:
            session.close()
            return

        results = self._get_all(session, subject)
        if not results:
            print('No scores.')
            session.close()
            return

        for i, r in enumerate(results, start=1):
            print(f"{i}. {r.exam_date}: {r.score_percent}%")

        numer = ask_int('Result number to delete', allow_empty=False, min_value=1)
        if numer is None or numer > len(results):
            print('Invalid number!')
            session.close()
            return

        target = results[numer - 1]
        if input('Are you sure you want to delete? (yes/no): ').strip().lower() != 'yes':
            print('Cancelled.')
            session.close()
            return

        session.delete(target)
        session.commit()
        print('Result deleted.')
        session.close()
