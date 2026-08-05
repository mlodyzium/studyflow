import json
import os

DATA_FILE = "data.json"


def data_read():
    """Funkcja, która wczytuje dane JSON z podanego DATA_FILE."""
    if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
        return {"subject": []}

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            print("USZKODZONY/NIEPOPRAWNY FORMAT JSON")
            return {"subject": []}


def data_write(data):
    """Funkcja, która nadpisuje plik DATA_FILE."""
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def add_subject():
    """Funkcja, dzięki której możesz dodać przedmiot do studyflow."""
    data = data_read()

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
        data_write(data)
        break


def add_tasks():
    """Funkcja, dzięki której możesz dodać dla danego przedmiotu zadanie."""
    data = data_read()

    if not data["subject"]:
        print("Brak przedmiotów!")
        return

    for subject in data["subject"]:
        print(f"ID[{subject['id']}] - Przedmiot: {subject['nazwa']}")

    while True:
        try:
            user_task_id = int(input("\nPodaj ID wybranego przedmiotu: "))
            if user_task_id not in range(len(data["subject"])):
                print("Podaj poprawne ID przedmiotu!")
                continue
            break
        except ValueError:
            print("Podaj liczbę!")

    while True:
        user_task = input("Podaj treść zadania: ").strip()
        
        if not user_task:
            print("Treść zadania nie może byc pusta!")
            continue
        else:
            break
    
    data["subject"][user_task_id]["zadania"].append({
        "id_task": len(data["subject"][user_task_id]["zadania"]),
        "task": user_task,
        "status": False
    })
    data_write(data)


def show_tasks():
    """Funkcja wyświetlająca listę wszystkich przedmiotów i zadań."""
    data = data_read()

    if not data["subject"]:
        print("Brak przedmiotów!")
        return

    for subject in data["subject"]:
        print(f"\nID[{subject['id']}] Przedmiot: {subject['nazwa']}")
        for task in subject["zadania"]:
            status_symbol = "Wykonane" if task["status"] else " "
            print(f"  [{status_symbol}] ID {task['id_task']}: {task['task']}")


def complete_task():
    """Funkcja oznaczająca zadanie jako wykonane."""
    data = data_read()

    if not data["subject"]:
        print("Brak przedmiotów!")
        return

    id_subject = None
    while True:
        try:
            for subject in data["subject"]:
                print(f"ID[{subject['id']}] - Przedmiot: {subject['nazwa']}")

            id_subject = get_user_int("przedmiotu, w którym chcesz ukończyć zadanie")

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
                print(f"  [{status_symbol}] ID {task['id_task']}: {task['task']}")
            break
        except (ValueError, IndexError):
            print("Błąd: Podaj poprawne ID!\n")

    while True:
        id_task = get_user_int("zadania, które wykonałeś")

        if not 0 <= id_task < len(data["subject"][id_subject]['zadania']):
            print("Błąd: Podaj poprawne ID!\n")
            continue 


        try:
            status = data["subject"][id_subject]["zadania"][id_task]["status"]
        except (ValueError, IndexError):
            print("Błąd!: Niepoprawne ID\n")
            continue

        if status:
            print("Zadanie już zostało wykonane!")
        else:
            data["subject"][id_subject]["zadania"][id_task]["status"] = True
            data_write(data)
            print("Zmieniono status zadania!")
        break


def get_user_int(typ):
    """Pobiera od użytkownika liczbę całkowitą (ID)."""
    while True:
        try:
            return int(input(f"\nPodaj ID {typ}: "))
        except ValueError:
            print("Błąd!: Podaj poprawne ID!")
