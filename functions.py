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


# ---------- Pomocnicze funkcje do pobierania danych od użytkownika ----------

def ask_date(prompt, allow_empty=True):
    """Prosi o datę w formacie YYYY-MM-DD. Zwraca date albo None (jeśli puste i dozwolone)."""
    while True:
        info = " (YYYY-MM-DD, enter aby pominąć)" if allow_empty else " (YYYY-MM-DD)"
        raw = input(f"{prompt}{info}: ").strip()
        if not raw and allow_empty:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()  # noqa: DTZ007
        except ValueError:
            print("Zły format daty! Użyj YYYY-MM-DD.")


def ask_int(prompt, allow_empty=True, min_value=None):
    while True:
        info = " (enter aby pominąć)" if allow_empty else ""
        raw = input(f"{prompt}{info}: ").strip()
        if not raw and allow_empty:
            return None
        try:
            value = int(raw)
            if min_value is not None and value < min_value:
                print(f"Wartość musi być >= {min_value}!")
                continue
            return value
        except ValueError:
            print("Podaj liczbę całkowitą!")


def ask_float(prompt, allow_empty=True, min_value=None, max_value=None):
    while True:
        info = " (enter aby pominąć)" if allow_empty else ""
        raw = input(f"{prompt}{info}: ").strip()
        if not raw and allow_empty:
            return None
        try:
            value = float(raw)
            if min_value is not None and value < min_value:
                print(f"Wartość musi być >= {min_value}!")
                continue
            if max_value is not None and value > max_value:
                print(f"Wartość musi być <= {max_value}!")
                continue
            return value
        except ValueError:
            print("Podaj liczbę!")


def ask_choice(prompt, options, allow_empty=True):
    while True:
        info = f" ({'/'.join(options)}, enter aby pominąć)" if allow_empty else f" ({'/'.join(options)})"
        raw = input(f"{prompt}{info}: ").strip().upper()
        if not raw and allow_empty:
            return None
        if raw in options:
            return raw
        print("Niepoprawna opcja!")


# ---------- Logowanie / rejestracja ----------

class Auth:
    def register(self):
        session = SessionLocal()

        while True:
            username = input("Wybierz nazwę użytkownika: ").strip().lower()
            if not username:
                print("Nazwa użytkownika nie może być pusta!")
                continue

            existing = session.query(User).filter(User.username == username).first()
            if existing:
                print("Taki użytkownik już istnieje!")
                continue
            break

        while True:
            password = getpass.getpass("Wybierz hasło: ")
            if len(password) < 4:
                print("Hasło musi mieć co najmniej 4 znaki!")
                continue

            if getpass.getpass("Powtórz hasło: ") != password:
                print("Hasła się nie zgadzają!")
                continue
            break

        new_user = User(username=username, password_hash=hash_password(password))
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        print(f"Zarejestrowano pomyślnie! Witaj, {username}.")

        user_uid = new_user.user_uid
        session.close()
        return user_uid

    def login(self):
        session = SessionLocal()

        while True:
            username = input("Nazwa użytkownika: ").strip().lower()
            password = getpass.getpass("Hasło: ")

            user = session.query(User).filter(User.username == username).first()

            if not user or not verify_password(password, user.password_hash):
                print("Błędna nazwa użytkownika lub hasło!")
                if input("Spróbować ponownie? (t/n): ").strip().lower() != "t":
                    session.close()
                    return None
                continue

            print(f"Zalogowano pomyślnie! Witaj, {username}.")
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

    def _select(self, session, prompt="Podaj nazwę przedmiotu"):
        subjects = self._get_all(session)
        if not subjects:
            print("Brak przedmiotów!")
            return None

        for s in subjects:
            data = f" (egzamin: {s.exam_date})" if s.exam_date else ""
            print(f"- {s.nazwa}{data}")

        while True:
            nazwa = input(f"\n{prompt} (albo 'anuluj'): ").strip().lower()
            if nazwa == "anuluj":
                return None
            subject = next((s for s in subjects if s.nazwa == nazwa), None)
            if not subject:
                print("Nie znaleziono przedmiotu o takiej nazwie!")
                continue
            return subject

    def add(self):
        session = SessionLocal()

        while True:
            nazwa = input("Podaj nazwę przedmiotu: ").strip().lower()
            if not nazwa:
                print("Nazwa nie może być pusta!")
                session.close()
                return

            if session.query(SubjectModel).filter(
                SubjectModel.user_uid == self.user_uid, SubjectModel.nazwa == nazwa
            ).first():
                print("Dany przedmiot już istnieje!")
                continue
            break

        exam_date = ask_date("Data egzaminu")

        new_subject = SubjectModel(nazwa=nazwa, user_uid=self.user_uid, exam_date=exam_date)
        session.add(new_subject)
        session.commit()
        print("Dodano przedmiot!")
        session.close()

    def edit(self):
        session = SessionLocal()
        subject = self._select(session, "Który przedmiot edytujesz?")
        if not subject:
            session.close()
            return

        nowa_nazwa = input(f"Nowa nazwa (enter aby zostawić '{subject.nazwa}'): ").strip().lower()
        if nowa_nazwa:
            exists = session.query(SubjectModel).filter(
                SubjectModel.user_uid == self.user_uid, SubjectModel.nazwa == nowa_nazwa
            ).first()
            if exists:
                print("Przedmiot o takiej nazwie już istnieje! Anulowano.")
                session.close()
                return
            subject.nazwa = nowa_nazwa

        nowa_data = ask_date("Nowa data egzaminu")
        if nowa_data:
            subject.exam_date = nowa_data

        session.commit()
        print("Zaktualizowano przedmiot!")
        session.close()

    def delete(self):
        session = SessionLocal()
        subject = self._select(session, "Który przedmiot usunąć?")
        if not subject:
            session.close()
            return

        if input(f"Na pewno usunąć '{subject.nazwa}' wraz ze wszystkim co zawiera? (tak/nie): ").strip().lower() != "tak":
            print("Anulowano.")
            session.close()
            return

        session.delete(subject)
        session.commit()
        print("Usunięto przedmiot.")
        session.close()

    def show(self):
        session = SessionLocal()
        subjects = self._get_all(session)
        if not subjects:
            print("Brak przedmiotów!")
        for s in subjects:
            data = f" (egzamin: {s.exam_date})" if s.exam_date else ""
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

    def _select(self, session, subject, prompt="Podaj nazwę tematu"):
        topics = self._get_all(session, subject)
        if not topics:
            print("Brak tematów w tym przedmiocie!")
            return None

        for t in topics:
            status = "opanowany" if t.status else "w trakcie"
            trudnosc = f", trudność: {t.difficulty}" if t.difficulty else ""
            print(f"- {t.nazwa} ({status}{trudnosc})")

        while True:
            nazwa = input(f"\n{prompt} (albo 'anuluj'): ").strip().lower()
            if nazwa == "anuluj":
                return None
            topic = next((t for t in topics if t.nazwa == nazwa), None)
            if not topic:
                print("Nie znaleziono tematu o takiej nazwie!")
                continue
            return topic

    def add(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "Do którego przedmiotu dodać temat?")
        if not subject:
            session.close()
            return

        while True:
            nazwa = input("Podaj nazwę tematu: ").strip().lower()
            if not nazwa:
                print("Nazwa nie może być pusta!")
                session.close()
                return
            if session.query(TopicModel).filter(
                TopicModel.subject_uid == subject.subject_uid, TopicModel.nazwa == nazwa
            ).first():
                print("Taki temat już istnieje w tym przedmiocie!")
                continue
            break

        difficulty = ask_choice("Poziom trudności", DIFFICULTY_OPTIONS)

        new_topic = TopicModel(nazwa=nazwa, subject_uid=subject.subject_uid, difficulty=difficulty)
        session.add(new_topic)
        session.commit()
        print("Dodano temat!")
        session.close()

    def edit(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "W którym przedmiocie edytujesz temat?")
        if not subject:
            session.close()
            return

        topic = self._select(session, subject, "Który temat edytujesz?")
        if not topic:
            session.close()
            return

        nowa_nazwa = input(f"Nowa nazwa (enter aby zostawić '{topic.nazwa}'): ").strip().lower()
        if nowa_nazwa:
            topic.nazwa = nowa_nazwa

        nowa_trudnosc = ask_choice("Nowy poziom trudności", DIFFICULTY_OPTIONS)
        if nowa_trudnosc:
            topic.difficulty = nowa_trudnosc

        zmiana_statusu = input("Oznaczyć jako opanowany? (tak/nie/enter aby pominąć): ").strip().lower()
        if zmiana_statusu == "tak":
            topic.status = True
        elif zmiana_statusu == "nie":
            topic.status = False

        session.commit()
        print("Zaktualizowano temat!")
        session.close()

    def delete(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "W którym przedmiocie usunąć temat?")
        if not subject:
            session.close()
            return

        topic = self._select(session, subject, "Który temat usunąć?")
        if not topic:
            session.close()
            return

        if input(f"Na pewno usunąć temat '{topic.nazwa}' wraz z zadaniami? (tak/nie): ").strip().lower() != "tak":
            print("Anulowano.")
            session.close()
            return

        session.delete(topic)
        session.commit()
        print("Usunięto temat.")
        session.close()

    def show(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "Tematy którego przedmiotu pokazać?")
        if not subject:
            session.close()
            return

        topics = self._get_all(session, subject)
        if not topics:
            print("Brak tematów.")
        for t in topics:
            status = "opanowany" if t.status else "w trakcie"
            trudnosc = f", trudność: {t.difficulty}" if t.difficulty else ""
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

    def _select_task(self, session, topic, prompt="Podaj treść zadania"):
        tasks = self._get_all(session, topic)
        if not tasks:
            print("Brak zadań w tym temacie!")
            return None

        for t in tasks:
            status = "Wykonane" if t.is_done else " "
            deadline = f", termin: {t.deadline.date()}" if t.deadline else ""
            print(f"  [{status}] {t.title} (priorytet: {t.priority.value}{deadline})")

        while True:
            tresc = input(f"\n{prompt} (albo 'anuluj'): ").strip()
            if tresc.lower() == "anuluj":
                return None
            matches = [t for t in tasks if t.title.strip().lower() == tresc.lower()]
            if not matches:
                print("Nie znaleziono zadania o takiej treści!")
                continue
            if len(matches) > 1:
                print("Kilka zadań ma taką samą treść — zmień nazwę jednego z nich.")
                continue
            return matches[0]

    def _pick_topic(self, session, subject):
        """Wybiera istniejący temat albo pozwala utworzyć nowy od razu."""
        topics = self.topics._get_all(session, subject)
        if topics:
            for t in topics:
                print(f"- {t.nazwa}")
            nazwa = input("\nPodaj nazwę tematu (istniejącego albo nowego): ").strip().lower()
        else:
            print("Ten przedmiot nie ma jeszcze żadnych tematów — utwórzmy pierwszy.")
            nazwa = input("Podaj nazwę nowego tematu: ").strip().lower()

        if not nazwa:
            print("Nazwa tematu nie może być pusta!")
            return None

        topic = next((t for t in topics if t.nazwa == nazwa), None)
        if topic:
            return topic

        difficulty = ask_choice("Poziom trudności nowego tematu", DIFFICULTY_OPTIONS)
        new_topic = TopicModel(nazwa=nazwa, subject_uid=subject.subject_uid, difficulty=difficulty)
        session.add(new_topic)
        session.commit()
        session.refresh(new_topic)
        return new_topic

    def add(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "Do którego przedmiotu dodać zadanie?")
        if not subject:
            session.close()
            return

        topic = self._pick_topic(session, subject)
        if not topic:
            session.close()
            return

        while True:
            title = input("Podaj treść zadania: ").strip()
            if not title:
                print("Treść nie może być pusta!")
                continue
            break

        deadline_date = ask_date("Termin wykonania")
        deadline = datetime.combine(deadline_date, datetime.min.time()) if deadline_date else None
        priority = ask_choice("Priorytet", PRIORITY_OPTIONS) or Priority.MEDIUM.value

        new_task = TaskModel(title=title, topic_uid=topic.topic_uid, deadline=deadline, priority=priority)
        session.add(new_task)
        session.commit()
        print("Dodano zadanie!")
        session.close()

    def edit(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "W którym przedmiocie edytujesz zadanie?")
        if not subject:
            session.close()
            return

        topic = self.topics._select(session, subject, "W którym temacie?")
        if not topic:
            session.close()
            return

        task = self._select_task(session, topic, "Które zadanie edytujesz?")
        if not task:
            session.close()
            return

        nowa_tresc = input(f"Nowa treść (enter aby zostawić '{task.title}'): ").strip()
        if nowa_tresc:
            task.title = nowa_tresc

        nowy_termin = ask_date("Nowy termin")
        if nowy_termin:
            task.deadline = datetime.combine(nowy_termin, datetime.min.time())

        nowy_priorytet = ask_choice("Nowy priorytet", PRIORITY_OPTIONS)
        if nowy_priorytet:
            task.priority = nowy_priorytet

        session.commit()
        print("Zaktualizowano zadanie!")
        session.close()

    def delete(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "W którym przedmiocie usunąć zadanie?")
        if not subject:
            session.close()
            return

        topic = self.topics._select(session, subject, "W którym temacie?")
        if not topic:
            session.close()
            return

        task = self._select_task(session, topic, "Które zadanie usunąć?")
        if not task:
            session.close()
            return

        if input(f"Na pewno usunąć '{task.title}'? (tak/nie): ").strip().lower() != "tak":
            print("Anulowano.")
            session.close()
            return

        session.delete(task)
        session.commit()
        print("Usunięto zadanie.")
        session.close()

    def complete(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "W którym przedmiocie?")
        if not subject:
            session.close()
            return

        topic = self.topics._select(session, subject, "W którym temacie?")
        if not topic:
            session.close()
            return

        task = self._select_task(session, topic, "Które zadanie wykonałeś?")
        if not task:
            session.close()
            return

        if task.is_done:
            print("Zadanie już zostało wykonane!")
        else:
            task.is_done = True
            session.commit()
            print("Zmieniono status zadania!")
        session.close()

    def show(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "Zadania którego przedmiotu pokazać?")
        if not subject:
            session.close()
            return

        topics = self.topics._get_all(session, subject)
        if not topics:
            print("Brak tematów (a więc i zadań).")
            session.close()
            return

        for topic in topics:
            print(f"\nTemat: {topic.nazwa}")
            tasks = self._get_all(session, topic)
            if not tasks:
                print("  (brak zadań)")
            for t in tasks:
                status = "Wykonane" if t.is_done else " "
                deadline = f", termin: {t.deadline.date()}" if t.deadline else ""
                print(f"  [{status}] {t.title} (priorytet: {t.priority.value}{deadline})")

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
        subject = self.subjects._select(session, "Dla którego przedmiotu zapisać sesję nauki?")
        if not subject:
            session.close()
            return

        duration = ask_int("Ile minut trwała sesja?", allow_empty=False, min_value=1)
        notes = input("Notatki (opcjonalnie): ").strip() or None

        new_session = StudySessionModel(
            subject_uid=subject.subject_uid,
            duration_minutes=duration,
            notes=notes,
        )
        session.add(new_session)
        session.commit()
        print("Zapisano sesję nauki!")
        session.close()

    def show(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "Sesje którego przedmiotu pokazać?")
        if not subject:
            session.close()
            return

        sessions = self._get_all(session, subject)
        if not sessions:
            print("Brak sesji nauki.")
        for s in sessions:
            notatka = f" — {s.notes}" if s.notes else ""
            print(f"- {s.started_at.strftime('%Y-%m-%d %H:%M')}, {s.duration_minutes} min{notatka}")
        session.close()

    def edit(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "W którym przedmiocie edytujesz sesję?")
        if not subject:
            session.close()
            return

        sessions = self._get_all(session, subject)
        if not sessions:
            print("Brak sesji nauki.")
            session.close()
            return

        for i, s in enumerate(sessions, start=1):
            notatka = f" — {s.notes}" if s.notes else ""
            print(f"{i}. {s.started_at.strftime('%Y-%m-%d %H:%M')}, {s.duration_minutes} min{notatka}")

        numer = ask_int("Numer sesji do edycji", allow_empty=False, min_value=1)
        if numer is None or numer > len(sessions):
            print("Niepoprawny numer!")
            session.close()
            return

        target = sessions[numer - 1]
        nowy_czas = ask_int("Nowy czas trwania (minuty)", min_value=1)
        if nowy_czas is not None:
            target.duration_minutes = nowy_czas

        nowe_notatki = input("Nowe notatki (enter aby zostawić bez zmian): ").strip()
        if nowe_notatki:
            target.notes = nowe_notatki

        session.commit()
        print("Zaktualizowano sesję!")
        session.close()

    def delete(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "W którym przedmiocie usunąć sesję?")
        if not subject:
            session.close()
            return

        sessions = self._get_all(session, subject)
        if not sessions:
            print("Brak sesji nauki.")
            session.close()
            return

        for i, s in enumerate(sessions, start=1):
            print(f"{i}. {s.started_at.strftime('%Y-%m-%d %H:%M')}, {s.duration_minutes} min")

        numer = ask_int("Numer sesji do usunięcia", allow_empty=False, min_value=1)
        if numer is None or numer > len(sessions):
            print("Niepoprawny numer!")
            session.close()
            return

        target = sessions[numer - 1]
        if input("Na pewno usunąć? (tak/nie): ").strip().lower() != "tak":
            print("Anulowano.")
            session.close()
            return

        session.delete(target)
        session.commit()
        print("Usunięto sesję.")
        session.close()


# ---------- Wyniki egzaminów ----------

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
        subject = self.subjects._select(session, "Dla którego przedmiotu zapisać wynik?")
        if not subject:
            session.close()
            return

        exam_date = ask_date("Data egzaminu", allow_empty=False)
        score = ask_float("Wynik w %", allow_empty=False, min_value=0, max_value=100)

        new_result = ExamResultModel(subject_uid=subject.subject_uid, exam_date=exam_date, score_percent=score)
        session.add(new_result)
        session.commit()
        print("Zapisano wynik egzaminu!")
        session.close()

    def show(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "Wyniki którego przedmiotu pokazać?")
        if not subject:
            session.close()
            return

        results = self._get_all(session, subject)
        if not results:
            print("Brak wyników.")
        for r in results:
            print(f"- {r.exam_date}: {r.score_percent}%")
        session.close()

    def edit(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "W którym przedmiocie edytujesz wynik?")
        if not subject:
            session.close()
            return

        results = self._get_all(session, subject)
        if not results:
            print("Brak wyników.")
            session.close()
            return

        for i, r in enumerate(results, start=1):
            print(f"{i}. {r.exam_date}: {r.score_percent}%")

        numer = ask_int("Numer wyniku do edycji", allow_empty=False, min_value=1)
        if numer is None or numer > len(results):
            print("Niepoprawny numer!")
            session.close()
            return

        target = results[numer - 1]
        nowa_data = ask_date("Nowa data egzaminu")
        if nowa_data:
            target.exam_date = nowa_data

        nowy_wynik = ask_float("Nowy wynik w %", min_value=0, max_value=100)
        if nowy_wynik is not None:
            target.score_percent = nowy_wynik

        session.commit()
        print("Zaktualizowano wynik!")
        session.close()

    def delete(self):
        session = SessionLocal()
        subject = self.subjects._select(session, "W którym przedmiocie usunąć wynik?")
        if not subject:
            session.close()
            return

        results = self._get_all(session, subject)
        if not results:
            print("Brak wyników.")
            session.close()
            return

        for i, r in enumerate(results, start=1):
            print(f"{i}. {r.exam_date}: {r.score_percent}%")

        numer = ask_int("Numer wyniku do usunięcia", allow_empty=False, min_value=1)
        if numer is None or numer > len(results):
            print("Niepoprawny numer!")
            session.close()
            return

        target = results[numer - 1]
        if input("Na pewno usunąć? (tak/nie): ").strip().lower() != "tak":
            print("Anulowano.")
            session.close()
            return

        session.delete(target)
        session.commit()
        print("Usunięto wynik.")
        session.close()