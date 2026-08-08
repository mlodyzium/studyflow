# StudyFlow 🎓

**StudyFlow** to lekka, modularna aplikacja konsolowa napisana w języku Python, służąca do organizacji nauki poprzez zarządzanie przedmiotami i przypisanymi do nich zadaniami. Aplikacja opiera się na architekturze zorientowanej obiektowo (OOP) z automatycznym zapisem stanu do pliku JSON (`data.json`) oraz wsparciem dla testów jednostkowych (`pytest`).

---

## 🏗️ Architektura i opis klas

Projekt został podzielony na odrębne pliki zgodnie z zasadą podziału odpowiedzialności (Separation of Concerns):

* **`main.py` (Interfejs i Nawigacja)**
  * Odpowiada za pętlę główną aplikacji, menu tekstowe oraz interakcję z użytkownikiem.
  * Korzysta z obiektów klas `Subject` oraz `Task` z modułu `functions.py`.
  * Normalizuje wprowadzane komendy (usuwanie spacji, zmiana na małe litery).

* **`functions.py` (Logika Biznesowa i Klasy Obiektowe)**
  * **`Data`**: Zarządza odczytem i zapisem danych do pliku `data.json` (wsparcie dla UTF-8, obsługa pustego lub uszkodzonego pliku JSON).
  * **`BaseManager`**: Klasa bazowa dostarczająca wspólny interfejs do operacji wczytywania (`load`) i zapisywania (`save`) danych dla dziedziczących klas.
  * **`Subject`** *(dziedziczy po `BaseManager`)*: Obsługuje dodawanie nowych przedmiotów oraz uniemożliwia tworzenie duplikatów.
  * **`Task`** *(dziedziczy po `BaseManager`)*: Zarządza zadaniami przypisanymi do przedmiotów – dodawanie zadań, ich wyświetlanie oraz oznaczanie jako wykonane.
  * **`Extras`**: Klasa z metodami pomocniczymi (np. `get_user_int`), zapewniająca walidację wejścia i odporność na błędy typu `ValueError`.

* **`test_functions.py` (Testy Jednostkowe)**
  * Zbiór zestawów testów napisanych przy użyciu frameworka `pytest`.
  * Pokrywa przypadki testowe dla klas `Data`, `Extras`, `Subject` oraz `Task`.
  * Wykorzystuje fixtures (`tmp_path`, `monkeypatch`) do izolacji środowiska testowego (operacje na plikach oraz symulacja wejścia `input()`).

---

## 📋 Lista Dostępnych Komend

| Komenda | Opis |
| :--- | :--- |
| `dodajprzedmiot` | Tworzy nowy przedmiot w systemie. |
| `dodajzadanie` | Dodaje zadanie do istniejącego przedmiotu na podstawie podanego ID. |
| `pokaz` | Wyświetla pełną listę przedmiotów wraz z zadaniami i ich statusami. |
| `wykonano` | Oznacza wskazane zadanie jako ukończone (`[Wykonane]`). |
| `wyjdz` | Zamyka program. |

---

## 🚀 Jak uruchomić program?

Do uruchomienia aplikacji wymagane jest wyłącznie zainstalowane środowisko **Python w wersji 3.8+**. Aplikacja korzysta z bibliotek standardowych (`json`, `os`).

### Krok 1: Pobranie kodu
Pobierz pliki projektu i upewnij się, że `main.py` oraz `functions.py` znajdują się w tym samym folderze.

### Krok 2: Uruchomienie w terminalu

1. Otwórz Terminal / Wiersz poleceń / PowerShell i przejdź do folderu z projektem:
   ```bash
   cd sciezka/do/folderu/studyflow
   python main.py
   ```

---

## 🛠️ Testy jednostkowe

Jeśli chcesz uruchamiać testy jednostkowe, zainstaluj w terminalu `pytest`:

```bash
pip install pytest

### Krok 1: Pobranie kodu
Pobierz pliki projektu i upewnij się, że `test_functions.py` oraz `functions.py` znajdują się w tym samym folderze.

### Krok 2: Uruchomienie w terminalu

1. Otwórz Terminal / Wiersz poleceń / PowerShell i przejdź do folderu z projektem:
   ```bash
   cd sciezka/do/folderu/studyflow
   py -m pytest test_functions.py
   ```


