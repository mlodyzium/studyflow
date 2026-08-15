import json
import os


class Data:

    def __init__(self):
        self.DATA_FILE = "data.json"

    def read(self):
        """Funkcja, która wczytuje dane JSON z podanego DATA_FILE."""
        if (not os.path.exists(self.DATA_FILE)
                or os.path.getsize(self.DATA_FILE) == 0):
            return {"subject": []}

        with open(self.DATA_FILE, "r", encoding="utf-8") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                print("USZKODZONY/NIEPOPRAWNY FORMAT JSON")
                return {"subject": []}

    def write(self, data):
        """Funkcja, która nadpisuje plik DATA_FILE."""
        with open(self.DATA_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)


class BaseManager:
    """
    Klasa bazowa - każda klasa, która po niej dziedziczy, automatycznie
    dostaje gotowy dostęp do wczytywania i zapisywania danych,
    bez potrzeby tworzenia Data() ręcznie w każdej metodzie.
    """

    def __init__(self):
        self.data_manager = Data()

    def load(self):
        return self.data_manager.read()

    def save(self, data):
        self.data_manager.write(data)


class Subject(BaseManager):
    def add(self):
        """Funkcja, dzięki której możesz dodać przedmiot do studyflow."""
        data = self.load()

        while True:
            user_subject = input("Podaj nazwę przedmiotu: ").strip().lower()

            if not user_subject:
                print("Nazwa przedmiotu nie może być pusta!")
                return

            if any(item["nazwa"] == user_subject for item in data["subject"]):
                print("Dany przedmiot już istnieje!")
                continue

            data["subject"].append({
                "id": len(data["subject"]),
                "nazwa": user_subject,
                "zadania": []
            })
            print("Pomyślnie dodano nowy przedmiot!")
            self.save(data)
            break


class Task(BaseManager):
    def add(self):
        """Funkcja, dzięki której możesz dodać dla danego przedmiotu zadanie."""
        data = self.load()

        if not data["subject"]:
            print("Brak przedmiotów!")
            return

        for subject in data["subject"]:
            print(f"ID[{subject['id']}] - Przedmiot: {subject['nazwa']}")

        while True:
            try:
                user_task_id = int(input("\nPodaj ID wybranego przedmiotu: "))
            except ValueError:
                print("Podaj liczbę!")
                continue

            if user_task_id not in range(len(data["subject"])):
                print("Podaj poprawne ID przedmiotu!")
                continue
            break

        while True:
            user_task = input("Podaj treść zadania: ").strip()

            if not user_task:
                print("Treść zadania nie może byc pusta!")
                continue

            print("Dodano zadanie pomyślnie!")
            break

        data["subject"][user_task_id]["zadania"].append({
            "id_task": len(data["subject"][user_task_id]["zadania"]),
            "task": user_task,
            "status": False
        })
        self.save(data)

    def show(self):
        """Funkcja wyświetlająca listę wszystkich przedmiotów i zadań."""
        data = self.load()

        if not data["subject"]:
            print("Brak przedmiotów!")
            return

        for subject in data["subject"]:
            print(f"\nID[{subject['id']}] Przedmiot: {subject['nazwa']}")
            for task in subject["zadania"]:
                status_symbol = "Wykonane" if task["status"] else " "
                print(f"  [{status_symbol}] ID {task['id_task']}: "
                      f"{task['task']}")

    def complete(self):
        """Funkcja oznaczająca zadanie jako wykonane."""
        data = self.load()
        extras = Extras()

        if not data["subject"]:
            print("Brak przedmiotów!")
            return

        while True:
            for subject in data["subject"]:
                print(f"ID[{subject['id']}] - Przedmiot: {subject['nazwa']}")

            id_subject = extras.get_user_int(
                "przedmiotu, w którym chcesz ukończyć zadanie"
            )

            if not 0 <= id_subject < len(data["subject"]):
                print("Błąd: Podaj poprawne ID!\n")
                continue

            if not data["subject"][id_subject]["zadania"]:
                print("Pusta lista zadań")
                return

            selected_subject = data["subject"][id_subject]
            print(f"Przedmiot: {selected_subject['nazwa']}")
            for task in selected_subject["zadania"]:
                status_symbol = "Wykonane" if task["status"] else " "
                print(f"  [{status_symbol}] ID {task['id_task']}: "
                      f"{task['task']}")
            break

        while True:
            id_task = extras.get_user_int("zadania, które wykonałeś")

            if not 0 <= id_task < len(data["subject"][id_subject]["zadania"]):
                print("Błąd: Podaj poprawne ID!\n")
                continue

            status = data["subject"][id_subject]["zadania"][id_task]["status"]

            if status:
                print("Zadanie już zostało wykonane!")
            else:
                data["subject"][id_subject]["zadania"][id_task]["status"] = True
                self.save(data)
                print("Zmieniono status zadania!")
            break


class Extras:
    def get_user_int(self, typ):
        """Pobiera od użytkownika liczbę całkowitą (ID)."""
        while True:
            try:
                return int(input(f"\nPodaj ID {typ}: "))
            except ValueError:
                print("Błąd!: Podaj poprawne ID!")