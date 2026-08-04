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

