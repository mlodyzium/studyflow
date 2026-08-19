# 📚 StudyFlow

StudyFlow to konsolowa aplikacja napisana w Pythonie, której celem jest ułatwienie organizacji nauki. Aplikacja pozwala użytkownikowi zarządzać przedmiotami, tematami i zadaniami, rejestrować sesje nauki oraz zapisywać wyniki egzaminów.

Projekt wykorzystuje **Python, SQLAlchemy oraz PostgreSQL**. Dane są przypisywane do konkretnych użytkowników, a dostęp do aplikacji zabezpiecza system rejestracji i logowania z hasłami przechowywanymi w postaci bezpiecznych hashy.

---

## ✨ Funkcje

### 🔐 Autoryzacja

* rejestracja nowych użytkowników,
* logowanie,
* walidacja danych logowania,
* hasła przechowywane jako hash przy użyciu `bcrypt`,
* oddzielne dane dla każdego użytkownika.

### 📚 Przedmioty

Dla każdego przedmiotu można:

* dodać nowy przedmiot,
* określić datę egzaminu,
* wyświetlić przedmioty,
* edytować dane,
* usunąć przedmiot.

Usunięcie przedmiotu usuwa również powiązane z nim dane.

### 📖 Tematy

Każdy przedmiot może posiadać wiele tematów.

Dla tematów dostępne są:

* dodawanie,
* wyświetlanie,
* edycja,
* usuwanie,
* określenie poziomu trudności:

  * `EASY`,
  * `MEDIUM`,
  * `HARD`,
* oznaczenie tematu jako opanowanego.

### ✅ Zadania

Zadania są przypisywane do konkretnych tematów.

Dostępne informacje:

* treść zadania,
* termin wykonania,
* priorytet:

  * `LOW`,
  * `MEDIUM`,
  * `HIGH`,
* status wykonania.

Dostępne operacje:

* dodawanie,
* wyświetlanie,
* edycja,
* usuwanie,
* oznaczanie jako wykonane.

Podczas dodawania zadania można również utworzyć nowy temat, jeśli nie istnieje jeszcze odpowiedni temat.

### ⏱️ Sesje nauki

StudyFlow umożliwia rejestrowanie czasu poświęconego na naukę.

Każda sesja może zawierać:

* przedmiot,
* datę i godzinę rozpoczęcia,
* czas trwania w minutach,
* opcjonalne notatki.

Sesje można:

* dodawać,
* wyświetlać,
* edytować,
* usuwać.

### 📝 Wyniki egzaminów

Dla każdego przedmiotu można zapisywać wyniki egzaminów.

Każdy wynik zawiera:

* datę egzaminu,
* wynik procentowy.

Wynik jest walidowany w zakresie `0–100%`.

---

## 🏗️ Struktura projektu

```text
studyflow/
│
├── data/
│   ├── auth.py
│   ├── database.py
│   └── models.py
│
├── functions.py
├── init_db.py
├── main.py
├── requirements.txt
├── test_functions.py
├── .gitignore
└── README.md
```

### `main.py`

Odpowiada za interfejs konsolowy oraz nawigację po aplikacji.

Zawiera:

* menu autoryzacji,
* menu główne,
* wspólne podmenu CRUD,
* obsługę przedmiotów,
* obsługę tematów,
* obsługę zadań,
* obsługę sesji nauki,
* obsługę wyników egzaminów.

### `functions.py`

Zawiera główną logikę aplikacji.

Najważniejsze klasy:

* `Auth` — rejestracja i logowanie,
* `SubjectService` — zarządzanie przedmiotami,
* `TopicService` — zarządzanie tematami,
* `TaskService` — zarządzanie zadaniami,
* `StudySessionService` — zarządzanie sesjami nauki,
* `ExamResultService` — zarządzanie wynikami egzaminów.

Znajdują się tutaj również funkcje pomocnicze odpowiedzialne za walidację danych wejściowych.

### `data/models.py`

Zawiera modele SQLAlchemy reprezentujące strukturę bazy danych:

* `User`,
* `Subject`,
* `Topic`,
* `Task`,
* `StudySession`,
* `ExamResult`,
* `Priority`.

Relacje pomiędzy modelami wykorzystują klucze obce oraz mechanizm `cascade`, dzięki czemu usunięcie nadrzędnego obiektu może automatycznie usunąć powiązane dane.

### `data/database.py`

Odpowiada za:

* konfigurację połączenia z PostgreSQL,
* utworzenie silnika SQLAlchemy,
* utworzenie `SessionLocal`,
* bazową klasę modeli `Base`.

Konfiguracja bazy danych jest pobierana ze zmiennych środowiskowych.

### `data/auth.py`

Zawiera funkcje:

* `hash_password()` — tworzenie hashy haseł,
* `verify_password()` — weryfikacja hasła.

Do obsługi haseł wykorzystywany jest `bcrypt`.

### `init_db.py`

Odpowiada za inicjalizację bazy danych.

Przed utworzeniem tabel sprawdza, czy wymagane tabele już istnieją. Jeśli nie, tworzy brakujące tabele na podstawie modeli SQLAlchemy.

---

## 🗄️ Baza danych

Projekt korzysta z **PostgreSQL**.

Schemat danych można uprościć do następującej struktury:

```text
User
 │
 └── Subject
      │
      ├── Topic
      │    │
      │    └── Task
      │
      ├── StudySession
      │
      └── ExamResult
```

Każdy użytkownik posiada własne przedmioty, a dane powiązane z przedmiotami są przechowywane w relacjach zależnych.

---

## ⚙️ Wymagania

Do uruchomienia projektu potrzebne są:

* Python 3.8+
* PostgreSQL
* pip

Wymagane biblioteki Python:

```text
sqlalchemy
psycopg2
python-dotenv
bcrypt
pytest
```

---

## 🔧 Konfiguracja

Przed uruchomieniem aplikacji należy utworzyć plik `.env` w głównym katalogu projektu.

Przykładowa konfiguracja:

```env
DB_USER=postgres
DB_PASSWORD=twoje_haslo
DB_HOST=localhost
DB_PORT=5432
DB_NAME=studyflow
```

Następnie należy utworzyć bazę danych PostgreSQL o nazwie odpowiadającej `DB_NAME`.

---

## 🚀 Uruchomienie

### 1. Pobranie repozytorium

```bash
git clone https://github.com/mlodyzium/studyflow.git
cd studyflow
```

### 2. Instalacja zależności

```bash
python3 -m pip install -r requirements.txt
```

### 3. Konfiguracja `.env`

Utwórz plik `.env` i uzupełnij dane dostępowe do PostgreSQL.

### 4. Inicjalizacja bazy

Można uruchomić:

```bash
python init_db.py
```

Program sprawdzi, czy wymagane tabele istnieją i utworzy je w razie potrzeby.

### 5. Uruchomienie aplikacji

```bash
python main.py
```

Po uruchomieniu pojawi się menu logowania:

```text
[1] Zaloguj się
[2] Zarejestruj się
[3] Wyjdź
```

---

## 🧪 Testy

Testy obejmują walidatory danych wejściowych, hashowanie i weryfikację haseł,
logowanie i rejestrację oraz kluczowe operacje zapisu danych w PostgreSQL.

Do uruchomienia testów integracyjnych potrzebna jest działająca testowa baza
PostgreSQL. Utwórz ją na przykład tak:

```bash
createdb -h localhost -U postgres studyflow_test
```

Następnie ustaw adres testowej bazy i uruchom pytest:

```bash
export TEST_DATABASE_URL="postgresql+psycopg2://postgres:TWOJE_HASLO@localhost:5432/studyflow_test"
python3 -m pytest -q
```

Testy tworzą wymagane tabele na początku działania, a po zakończeniu usuwają
je z testowej bazy. Ostatni zweryfikowany wynik:

```text
10 passed, 6 warnings in 1.23s
```

Ostrzeżenia dotyczą użycia `datetime.utcnow()` w SQLAlchemy i nie powodują
niepowodzenia testów.

---

## 🧭 Główne menu

Po zalogowaniu użytkownik otrzymuje dostęp do:

```text
[przedmioty] - Zarządzaj przedmiotami
[tematy]     - Zarządzaj tematami
[zadania]    - Zarządzaj zadaniami
[sesje]      - Sesje nauki
[egzaminy]   - Wyniki egzaminów
[wyloguj]    - Wyloguj się
```

Dla większości modułów dostępne są operacje:

```text
[dodaj]
[edytuj]
[usun]
[pokaz]
[wroc]
```

---

## 🛠️ Technologie

Projekt wykorzystuje:

* **Python** — główny język programowania,
* **SQLAlchemy** — ORM i obsługa modeli bazy danych,
* **PostgreSQL** — baza danych,
* **psycopg2** — połączenie Pythona z PostgreSQL,
* **python-dotenv** — obsługa zmiennych środowiskowych,
* **bcrypt** — bezpieczne haszowanie haseł,
* **pytest** — testy jednostkowe.

---

## 🔒 Bezpieczeństwo

Dane dostępowe do bazy danych nie są przechowywane bezpośrednio w kodzie.

Konfiguracja znajduje się w pliku `.env`, który jest dodany do `.gitignore`.

Hasła użytkowników nie są zapisywane w bazie w postaci jawnego tekstu — przed zapisaniem są haszowane przy użyciu `bcrypt`.

---

## 🚧 Planowany rozwój

Możliwe dalsze rozszerzenia projektu:

* aktualizacja testów do nowej architektury,
* rozbudowanie obsługi błędów połączenia z bazą,
* graficzny interfejs użytkownika.

##
