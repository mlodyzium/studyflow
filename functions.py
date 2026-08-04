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
