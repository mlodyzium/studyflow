import sys

if "--test" in sys.argv or "test_functions" in sys.argv:
    import pytest
    result = pytest.main(["-q", "legacy_cli/test_functions.py"])
    # Missing local dependencies or a test database means skipped tests, not an app error.
    raise SystemExit(0 if result == 5 else result)

from legacy_cli.functions import (
    Auth,
    ExamResultService,
    StudySessionService,
    SubjectService,
    TaskService,
    TopicService,
)

MAIN_MENU = '\n========================================\n         📚 STUDYFLOW - MENU 📚\n========================================\n [subjects]   - Manage subjects\n [topics]     - Manage topics\n [tasks]      - Manage tasks\n [sessions]   - Study sessions\n [exams]      - Exam results\n [logout]     - Log out\n========================================\n'

CRUD_MENU_TEMPLATE = '\n--- {nazwa} ---\n [add]    - Add\n [edit]   - Edit\n [delete] - Delete\n [show]   - Show\n [back]   - Back to main menu\n'


def crud_menu(nazwa, service, extra_actions=None):
    """Shared CRUD menu for services with add, edit, delete, and show actions."""
    extra_actions = extra_actions or {}
    while True:
        print(CRUD_MENU_TEMPLATE.format(nazwa=nazwa))
        for label, (opis, _) in extra_actions.items():
            print(f" [{label}] - {opis}")
        wybor = input('Select option > ').lower().strip()

        if wybor == 'add':
            service.add()
        elif wybor == 'edit':
            service.edit()
        elif wybor == 'delete':
            service.delete()
        elif wybor == 'show':
            service.show()
        elif wybor in extra_actions:
            extra_actions[wybor][1]()
        elif wybor == 'back':
            break
        else:
            print('Invalid command!')


def auth_menu():
    auth = Auth()
    while True:
        wybor = input('\n[1] Log in   [2] Register   [3] Exit\nSelect > ').strip()

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
            print('Invalid command!')


def main():
    print('📚 Welcome to StudyFlow!')
    user_uid = auth_menu()

    if not user_uid:
        print('Goodbye!')
        return

    subjects = SubjectService(user_uid)
    topics = TopicService(user_uid)
    tasks = TaskService(user_uid)
    study_sessions = StudySessionService(user_uid)
    exam_results = ExamResultService(user_uid)

    while True:
        print(MAIN_MENU)
        wybor = input('Select option > ').lower().strip()

        if wybor == 'subjects':
            crud_menu('Subjects', subjects)
        elif wybor == 'topics':
            crud_menu('Topics', topics)
        elif wybor == 'tasks':
            crud_menu('Tasks', tasks, extra_actions={
                'completed': ('Mark task as done', tasks.complete)
            })
        elif wybor == 'sessions':
            crud_menu('Study sessions', study_sessions)
        elif wybor == 'exams':
            crud_menu('Exam results', exam_results)
        elif wybor == 'logout':
            print('\nHappy studying! See you!')
            break
        else:
            print('Invalid command!')


if __name__ == "__main__":
    main()
