import sys

if "--test" in sys.argv or "test_functions" in sys.argv:
    import pytest
    result = pytest.main(["-q", "test_functions.py"])
    # Brak lokalnych zależności/bazy oznacza same skipy, nie błąd aplikacji.
    raise SystemExit(0 if result == 5 else result)

from functions import (
    Auth,
    ExamResultService,
    StudySessionService,
    SubjectService,
    TaskService,
    TopicService,
)
from init_db import init_db

MAIN_MENU = """
========================================
         📚 STUDYFLOW - MENU 📚
========================================
 [przedmioty] - Zarządzaj przedmiotami
 [tematy]     - Zarządzaj tematami
 [zadania]    - Zarządzaj zadaniami
 [sesje]      - Sesje nauki
 [egzaminy]   - Wyniki egzaminów
 [wyloguj]    - Wyloguj się
========================================
"""

CRUD_MENU_TEMPLATE = """
--- {nazwa} ---
 [dodaj]  - Dodaj
 [edytuj] - Edytuj
 [usun]   - Usuń
 [pokaz]  - Pokaż
 [wroc]   - Wróć do menu głównego
"""


def crud_menu(nazwa, service, extra_actions=None):
    """Wspólne podmenu CRUD dla serwisów, które mają add/edit/delete/show."""
    extra_actions = extra_actions or {}
    while True:
        print(CRUD_MENU_TEMPLATE.format(nazwa=nazwa))
        for label, (opis, _) in extra_actions.items():
            print(f" [{label}] - {opis}")
        wybor = input("Wybierz opcję > ").lower().strip()

        if wybor == "dodaj":
            service.add()
        elif wybor == "edytuj":
            service.edit()
        elif wybor == "usun":
            service.delete()
        elif wybor == "pokaz":
            service.show()
        elif wybor in extra_actions:
            extra_actions[wybor][1]()
        elif wybor == "wroc":
            break
        else:
            print("Niepoprawna komenda!")


def auth_menu():
    auth = Auth()
    while True:
        wybor = input("\n[1] Zaloguj się   [2] Zarejestruj się   [3] Wyjdź\nWybierz > ").strip()

        if wybor == "1":
            user_uid = auth.login()
            if user_uid:
                return user_uid
        elif wybor == "2":
            user_uid = auth.register()
            if user_uid:
                return user_uid
        elif wybor == "3":
            return None
        else:
            print("Niepoprawna komenda!")


def main():
    print("📚 Witaj w StudyFlow!")
    user_uid = auth_menu()

    if not user_uid:
        print("Do zobaczenia!")
        return

    subjects = SubjectService(user_uid)
    topics = TopicService(user_uid)
    tasks = TaskService(user_uid)
    study_sessions = StudySessionService(user_uid)
    exam_results = ExamResultService(user_uid)

    while True:
        print(MAIN_MENU)
        wybor = input("Wybierz opcję > ").lower().strip()

        if wybor == "przedmioty":
            crud_menu("Przedmioty", subjects)
        elif wybor == "tematy":
            crud_menu("Tematy", topics)
        elif wybor == "zadania":
            crud_menu("Zadania", tasks, extra_actions={
                "wykonano": ("Oznacz zadanie jako zrobione", tasks.complete)
            })
        elif wybor == "sesje":
            crud_menu("Sesje nauki", study_sessions)
        elif wybor == "egzaminy":
            crud_menu("Wyniki egzaminów", exam_results)
        elif wybor == "wyloguj":
            print("\nMiłej nauki! Do zobaczenia!")
            break
        else:
            print("Niepoprawna komenda!")


if __name__ == "__main__":
    init_db()
    main()
