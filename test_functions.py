import json

import pytest

from functions import Data, Extras, Subject, Task

# ---------------------------------------------------------------------------
# FIXTURES / HELPERY
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolate_cwd(tmp_path, monkeypatch):
    """
    Uruchamia KAŻDY test w świeżym, tymczasowym folderze roboczym.
    Subject/Task/Extras tworzą wewnętrznie Data() z domyślną, względną
    ścieżką "data.json" - dzięki chdir() ten plik zawsze powstaje
    w tmp_path, a nie w prawdziwym projekcie.
    autouse=True => nie trzeba tej fixture wpisywać w każdym teście ręcznie.
    """
    monkeypatch.chdir(tmp_path)


def fake_input(monkeypatch, values):
    """
    Podmienia wbudowaną funkcję input() tak, żeby przy kolejnych wywołaniach
    zwracała kolejne elementy z listy `values`, zamiast czekać na klawiaturę.
    """
    it = iter(values)
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: next(it))


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

class TestData:

    def test_read_when_file_missing(self):
        d = Data()
        assert d.read() == {"subject": []}

    def test_read_when_file_empty(self, tmp_path):
        (tmp_path / "data.json").write_text("")
        d = Data()
        assert d.read() == {"subject": []}

    def test_read_when_file_corrupted(self, tmp_path, capsys):
        (tmp_path / "data.json").write_text("{to nie jest poprawny json")
        d = Data()
        result = d.read()
        captured = capsys.readouterr()
        assert result == {"subject": []}
        assert "USZKODZONY" in captured.out

    def test_write_then_read_roundtrip(self):
        d = Data()
        sample = {"subject": [{"id": 0, "nazwa": "matematyka", "zadania": []}]}
        d.write(sample)
        assert d.read() == sample

    def test_write_creates_valid_json_file(self, tmp_path):
        d = Data()
        d.write({"subject": []})
        with open(tmp_path / "data.json", "r", encoding="utf-8") as f:
            content = json.load(f)
        assert content == {"subject": []}


# ---------------------------------------------------------------------------
# Extras
# ---------------------------------------------------------------------------

class TestExtras:

    def test_get_user_int_valid_input(self, monkeypatch):
        fake_input(monkeypatch, ["3"])
        extras = Extras()
        assert extras.get_user_int("testu") == 3

    def test_get_user_int_retries_on_invalid_input(self, monkeypatch, capsys):
        # "abc" i "" to nie liczby -> ValueError -> pętla próbuje dalej
        fake_input(monkeypatch, ["abc", "", "7"])
        extras = Extras()
        result = extras.get_user_int("testu")
        captured = capsys.readouterr()
        assert result == 7
        assert captured.out.count("Podaj poprawne ID!") == 2


# ---------------------------------------------------------------------------
# Subject
# ---------------------------------------------------------------------------

class TestSubjectAdd:

    def test_add_new_subject(self, monkeypatch):
        fake_input(monkeypatch, ["Matematyka"])
        subject = Subject()
        subject.add()

        data = Data().read()
        assert len(data["subject"]) == 1
        assert data["subject"][0]["nazwa"] == "matematyka"  # .lower() w kodzie
        assert data["subject"][0]["id"] == 0
        assert data["subject"][0]["zadania"] == []

    def test_add_empty_name(self, monkeypatch, capsys):
        fake_input(monkeypatch, [""])
        subject = Subject()
        subject.add()

        captured = capsys.readouterr()
        data = Data().read()
        assert data["subject"] == []
        assert "nie może być pusta" in captured.out

    def test_add_duplicate_subject(self, monkeypatch, capsys):
        Data().write({"subject": [{"id": 0, "nazwa": "matematyka", "zadania": []}]})
        # pierwsze wejście = duplikat -> continue; drugie = nowy przedmiot -> break
        fake_input(monkeypatch, ["matematyka", "fizyka"])

        subject = Subject()
        subject.add()

        captured = capsys.readouterr()
        data = Data().read()
        assert "już istnieje" in captured.out
        assert len(data["subject"]) == 2
        assert data["subject"][1]["nazwa"] == "fizyka"


# ---------------------------------------------------------------------------
# Task.add
# ---------------------------------------------------------------------------

class TestTaskAdd:

    def test_add_task_no_subjects(self, capsys):
        task = Task()
        task.add()
        captured = capsys.readouterr()
        assert "Brak przedmiotów!" in captured.out

    def test_add_task_success(self, monkeypatch):
        Data().write({"subject": [{"id": 0, "nazwa": "matematyka", "zadania": []}]})
        fake_input(monkeypatch, ["0", "Zrobić zadanie domowe"])

        task = Task()
        task.add()

        data = Data().read()
        zadania = data["subject"][0]["zadania"]
        assert len(zadania) == 1
        assert zadania[0]["task"] == "Zrobić zadanie domowe"
        assert zadania[0]["status"] is False
        assert zadania[0]["id_task"] == 0

    def test_add_task_invalid_id_then_valid(self, monkeypatch, capsys):
        Data().write({"subject": [{"id": 0, "nazwa": "matematyka", "zadania": []}]})
        # "abc" -> ValueError, "5" -> poza zakresem, "0" -> OK
        fake_input(monkeypatch, ["abc", "5", "0", "Nauka na kolokwium"])

        task = Task()
        task.add()

        captured = capsys.readouterr()
        data = Data().read()
        assert "Podaj liczbę!" in captured.out
        assert "Podaj poprawne ID przedmiotu!" in captured.out
        assert len(data["subject"][0]["zadania"]) == 1

    def test_add_task_empty_content_then_valid(self, monkeypatch, capsys):
        Data().write({"subject": [{"id": 0, "nazwa": "matematyka", "zadania": []}]})
        fake_input(monkeypatch, ["0", "", "Przeczytać rozdział 3"])

        task = Task()
        task.add()

        captured = capsys.readouterr()
        data = Data().read()
        assert "nie może byc pusta" in captured.out
        assert data["subject"][0]["zadania"][0]["task"] == "Przeczytać rozdział 3"

    def test_add_task_negative_id_then_valid(self, monkeypatch, capsys):
        Data().write({"subject": [{"id": 0, "nazwa": "matematyka", "zadania": []}]})
        # "-1" -> nie powinno wskazywać na ostatni element listy (poza zakresem), "0" -> OK
        fake_input(monkeypatch, ["-1", "0", "Nauka na kolokwium"])

        task = Task()
        task.add()

        captured = capsys.readouterr()
        data = Data().read()

        # -1 nie może zostać zaakceptowane jako poprawne ID
        assert "Podaj poprawne ID przedmiotu!" in captured.out

        # zadanie powinno trafić do przedmiotu o id=0, a nie zniknąć/trafić gdzie indziej
        assert len(data["subject"][0]["zadania"]) == 1
        assert data["subject"][0]["zadania"][0]["task"] == "Nauka na kolokwium"

    def test_add_task_negative_id_does_not_target_last_subject(self, monkeypatch, capsys):
        Data().write({
            "subject": [
                {"id": 0, "nazwa": "matematyka", "zadania": []},
                {"id": 1, "nazwa": "fizyka", "zadania": []},
            ]
        })
        # -1 mogłoby (błędnie) wskazywać na "fizyka" (ostatni element listy), jeśli walidacja by zawiodła
        fake_input(monkeypatch, ["-1", "1", "Powtorka wzorow"])

        task = Task()
        task.add()

        captured = capsys.readouterr()
        data = Data().read()

        assert "Podaj poprawne ID przedmiotu!" in captured.out
        # zadanie trafiło tam, gdzie faktycznie chcieliśmy (id=1), a nie przez przypadek przez -1
        assert len(data["subject"][1]["zadania"]) == 1
        assert len(data["subject"][0]["zadania"]) == 0

    def test_complete_negative_subject_id_then_valid(self, monkeypatch, capsys):
        Data().write({
            "subject": [
                {"id": 0, "nazwa": "matematyka", "zadania": [
                    {"id_task": 0, "task": "Zadanie 1", "status": False}
                ]},
            ]
        })
        # "-1" -> poza zakresem, "0" -> OK, potem id_task = "0"
        fake_input(monkeypatch, ["-1", "0", "0"])

        task = Task()
        task.complete()

        captured = capsys.readouterr()
        data = Data().read()

        assert "Błąd: Podaj poprawne ID!" in captured.out
        assert data["subject"][0]["zadania"][0]["status"] is True


    def test_complete_negative_subject_id_does_not_target_last_subject(self, monkeypatch, capsys):
        Data().write({
            "subject": [
                {"id": 0, "nazwa": "matematyka", "zadania": [
                    {"id_task": 0, "task": "Zadanie 1", "status": False}
                ]},
                {"id": 1, "nazwa": "fizyka", "zadania": [
                    {"id_task": 0, "task": "Zadanie 2", "status": False}
                ]},
            ]
        })
        # -1 mogłoby (błędnie) wskazywać na "fizyka" (ostatni przedmiot), gdyby walidacja zawiodła
        fake_input(monkeypatch, ["-1", "1", "0"])

        task = Task()
        task.complete()

        captured = capsys.readouterr()
        data = Data().read()

        assert "Błąd: Podaj poprawne ID!" in captured.out
        # zmienione zostało zadanie w przedmiocie o id=1, a nie przypadkiem gdzie indziej
        assert data["subject"][1]["zadania"][0]["status"] is True
        assert data["subject"][0]["zadania"][0]["status"] is False


    def test_complete_negative_task_id_then_valid(self, monkeypatch, capsys):
        Data().write({
            "subject": [
                {"id": 0, "nazwa": "matematyka", "zadania": [
                    {"id_task": 0, "task": "Zadanie 1", "status": False},
                    {"id_task": 1, "task": "Zadanie 2", "status": False},
                ]},
            ]
        })
        # id_subject = "0" (OK), potem id_task: "-1" -> poza zakresem, "1" -> OK
        fake_input(monkeypatch, ["0", "-1", "1"])

        task = Task()
        task.complete()

        captured = capsys.readouterr()
        data = Data().read()

        assert "Błąd: Podaj poprawne ID!" in captured.out
        # -1 nie mogło (błędnie) oznaczyć ostatniego zadania na liście (id_task=1) zamiast dopiero po walidacji
        assert data["subject"][0]["zadania"][1]["status"] is True
        assert data["subject"][0]["zadania"][0]["status"] is False
# ---------------------------------------------------------------------------
# Task.show
# ---------------------------------------------------------------------------

class TestTaskShow:

    def test_show_no_subjects(self, capsys):
        task = Task()
        task.show()
        captured = capsys.readouterr()
        assert "Brak przedmiotów!" in captured.out

    def test_show_with_subject_and_task(self, capsys):
        Data().write({"subject": [{
            "id": 0, "nazwa": "matematyka",
            "zadania": [{"id_task": 0, "task": "Zrobić zadanie", "status": False}]
        }]})
        task = Task()
        task.show()

        captured = capsys.readouterr()
        assert "matematyka" in captured.out
        assert "Zrobić zadanie" in captured.out


# ---------------------------------------------------------------------------
# Task.complete
# ---------------------------------------------------------------------------

class TestTaskComplete:

    def test_complete_marks_task_as_done(self, monkeypatch):
        """
        Bug z Extras.get_user_int(...) (bez self) zamiast extras.get_user_int(...)
        został naprawiony w wersji z BaseManager - complete() teraz poprawnie
        oznacza zadanie jako wykonane.
        """
        Data().write({"subject": [{
            "id": 0, "nazwa": "matematyka",
            "zadania": [{"id_task": 0, "task": "Zrobić zadanie", "status": False}]
        }]})
        fake_input(monkeypatch, ["0", "0"])

        task = Task()
        task.complete()

        data = Data().read()
        assert data["subject"][0]["zadania"][0]["status"] is True

    def test_complete_already_done_task(self, monkeypatch, capsys):
        Data().write({"subject": [{
            "id": 0, "nazwa": "matematyka",
            "zadania": [{"id_task": 0, "task": "Zrobić zadanie", "status": True}]
        }]})
        fake_input(monkeypatch, ["0", "0"])

        task = Task()
        task.complete()

        captured = capsys.readouterr()
        assert "już zostało wykonane" in captured.out
