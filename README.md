# StudyFlow 🎓

**StudyFlow** to aplikacja konsolowa w języku Python przeznaczona do zarządzania przedmiotami oraz przypisanymi do nich zadaniami. Wszystkie dane są automatycznie zapisywane w lokalnym pliku JSON.

---

## 🛠️ Funkcjonalności

* **Dodawanie przedmiotów** – tworzenie nowych przedmiotów z weryfikacją unikalności nazw.
* **Dodawanie zadań** – przypisywanie zadań do wybranych przedmiotów.
* **Podgląd zadań** – wyświetlanie listy przedmiotów wraz ze stanem realizacji (`[ ]` / `[Wykonane]`).
* **Ukończenie zadań** – zmiana statusu zadań na wykonane.
* **Trwałość danych** – automatyczny zapis i odczyt z pliku `data.json`.
* **Walidacja danych** – zabezpieczenie przed wprowadzaniem niepoprawnych danych w konsoli.

---

## 🚀 Uruchomienie

Wymagany jest Python w wersji **3.x**. Aplikacja korzysta z wbudowanych bibliotek (`json`, `os`).

1. Pobierz pliki projektu.
2. Uruchom program w terminalu:
   ```bash
   python main.py