# StudyFlow API

StudyFlow to backend aplikacji wspierającej organizację nauki. Pozwala zarządzać
użytkownikami, przedmiotami, tematami oraz zadaniami przez REST API. Projekt
korzysta z FastAPI, Pydantic, SQLAlchemy, PostgreSQL oraz Alembic.

API udostępnia pełny CRUD dla głównych zasobów, automatyczną dokumentację
Swagger, walidację danych i bezpieczne hashowanie haseł przy użyciu Argon2.

## Najważniejsze możliwości

- tworzenie, pobieranie, edycja i usuwanie użytkowników,
- przypisywanie przedmiotów do użytkowników,
- przypisywanie tematów do przedmiotów,
- tworzenie zadań z terminem, statusem i priorytetem,
- filtrowanie przedmiotów, tematów i zadań po obiektach nadrzędnych,
- walidacja requestów i odpowiedzi przez Pydantic,
- obsługa błędów HTTP, między innymi `404`, `409` i `422`,
- migracje schematu PostgreSQL za pomocą Alembic,
- testy API uruchamiane na izolowanej bazie SQLite.

## Technologie

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic
- SQLAlchemy 2
- PostgreSQL i Psycopg 3
- Alembic
- pwdlib z Argon2
- pytest i HTTPX

## Architektura

Żądanie przechodzi przez aplikację w następujący sposób:

```text
Swagger / frontend / klient HTTP
              |
              v
         FastAPI router
              |
              v
       Pydantic schema
              |
              v
       service biznesowy
              |
              v
          SQLAlchemy
              |
              v
          PostgreSQL
```

Router odpowiada za komunikację HTTP, schemat Pydantic za walidację, service za
logikę biznesową, a model SQLAlchemy za odwzorowanie tabel PostgreSQL.

## Struktura projektu

```text
studyflow/
├── alembic/                 # środowisko i wersje migracji
│   └── versions/            # kolejne zmiany schematu bazy
├── app/
│   ├── core/                # konfiguracja i bezpieczeństwo
│   ├── db/                  # engine, sesje i zależność get_db
│   ├── models/              # modele SQLAlchemy
│   ├── routers/             # endpointy FastAPI
│   ├── schemas/             # schematy requestów i odpowiedzi
│   ├── services/            # logika biznesowa i operacje CRUD
│   └── main.py              # punkt wejścia aplikacji
├── data/                    # kompatybilność ze starszymi importami
├── legacy_cli/              # archiwalna wersja konsolowa
├── tests/                   # testy API
├── .env.example             # przykład konfiguracji
├── alembic.ini              # konfiguracja Alembic
└── requirements.txt         # zależności projektu
```

## Instalacja

Sklonuj repozytorium i przejdź do jego katalogu:

```powershell
git clone https://github.com/mlodyzium/studyflow.git
cd studyflow
```

Utwórz i aktywuj środowisko wirtualne:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Zainstaluj zależności:

```powershell
python -m pip install -r requirements.txt
```

## Konfiguracja PostgreSQL

Utwórz `.env` w głównym katalogu projektu na podstawie `.env.example`:

```powershell
Copy-Item .env.example .env
```

Uzupełnij dane dostępowe:

```env
APP_NAME=StudyFlow API
DB_USER=postgres
DB_PASSWORD=twoje_haslo
DB_HOST=localhost
DB_PORT=5432
DB_NAME=studyflow
```

Zamiast osobnych zmiennych możesz ustawić pełny adres połączenia:

```env
DATABASE_URL=postgresql+psycopg://postgres:twoje_haslo@localhost:5432/studyflow
```

Plik `.env` zawiera dane poufne i jest ignorowany przez Git. Do repozytorium
należy dodawać wyłącznie `.env.example` bez prawdziwego hasła.

## Migracje bazy danych

Dla nowej, pustej bazy zastosuj wszystkie migracje:

```powershell
alembic upgrade head
```

Projekt posiada migrację początkową `20260907_01`, która tworzy tabele:

- `users`,
- `subjects`,
- `topics`,
- `tasks`,
- `study_sessions`,
- `exam_results`.

Jeżeli baza ma już zgodne tabele, nie uruchamiaj na niej migracji początkowej
tworzącej je ponownie. Oznacz istniejący schemat jako aktualny:

```powershell
alembic stamp head
```

Nową migrację po zmianie modeli utworzysz poleceniem:

```powershell
alembic revision --autogenerate -m "opis zmiany"
```

Przed zastosowaniem zawsze przeczytaj wygenerowany plik. Następnie wykonaj:

```powershell
alembic upgrade head
```

Przydatne polecenia:

```powershell
alembic current
alembic history
alembic check
alembic downgrade -1
```

## Uruchomienie API

```powershell
uvicorn app.main:app --reload
```

Po uruchomieniu dostępne są:

- API: `http://127.0.0.1:8000`,
- Swagger UI: `http://127.0.0.1:8000/docs`,
- ReDoc: `http://127.0.0.1:8000/redoc`,
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`,
- kontrola działania: `http://127.0.0.1:8000/health`.

Endpoint zdrowia powinien zwrócić:

```json
{
  "status": "ok"
}
```

## Model danych

Główna hierarchia danych wygląda następująco:

```text
User
└── Subject
    ├── Topic
    │   └── Task
    ├── StudySession
    └── ExamResult
```

Dlatego typowa kolejność tworzenia danych to użytkownik, przedmiot, temat i
zadanie. UUID zwrócone przez jeden endpoint jest przekazywane do następnego.

## Endpointy

| Metoda | Endpoint | Opis |
| --- | --- | --- |
| `GET` | `/health` | Sprawdzenie działania API |
| `POST` | `/users` | Utworzenie użytkownika |
| `GET` | `/users` | Lista użytkowników |
| `GET` | `/users/{user_uid}` | Pobranie użytkownika |
| `PATCH` | `/users/{user_uid}` | Częściowa edycja użytkownika |
| `DELETE` | `/users/{user_uid}` | Usunięcie użytkownika |
| `POST` | `/subjects` | Utworzenie przedmiotu |
| `GET` | `/subjects` | Lista lub filtrowanie przedmiotów |
| `GET` | `/subjects/{subject_uid}` | Pobranie przedmiotu |
| `PATCH` | `/subjects/{subject_uid}` | Edycja przedmiotu |
| `DELETE` | `/subjects/{subject_uid}` | Usunięcie przedmiotu |
| `POST` | `/topics` | Utworzenie tematu |
| `GET` | `/topics` | Lista lub filtrowanie tematów |
| `GET` | `/topics/{topic_uid}` | Pobranie tematu |
| `PATCH` | `/topics/{topic_uid}` | Edycja tematu |
| `DELETE` | `/topics/{topic_uid}` | Usunięcie tematu |
| `POST` | `/tasks` | Utworzenie zadania |
| `GET` | `/tasks` | Lista lub filtrowanie zadań |
| `GET` | `/tasks/{task_uid}` | Pobranie zadania |
| `PATCH` | `/tasks/{task_uid}` | Edycja zadania |
| `DELETE` | `/tasks/{task_uid}` | Usunięcie zadania |

## Przykładowy przepływ w Swaggerze

### 1. Utworzenie użytkownika

`POST /users`

```json
{
  "username": "student",
  "password": "bezpieczne-haslo",
  "email": "student@example.com"
}
```

Hasło jest hashowane algorytmem Argon2. API nigdy nie zwraca hasła ani
`password_hash` w odpowiedzi.

### 2. Utworzenie przedmiotu

`POST /subjects`

```json
{
  "name": "Matematyka",
  "user_uid": "UUID_UŻYTKOWNIKA",
  "exam_date": "2026-12-20"
}
```

### 3. Utworzenie tematu

`POST /topics`

```json
{
  "name": "Algebra",
  "subject_uid": "UUID_PRZEDMIOTU",
  "difficulty": "medium"
}
```

### 4. Utworzenie zadania

`POST /tasks`

```json
{
  "title": "Powtórzyć równania kwadratowe",
  "topic_uid": "UUID_TEMATU",
  "deadline": "2026-09-15T18:00:00",
  "priority": "HIGH"
}
```

Dopuszczalne priorytety to `LOW`, `MEDIUM` i `HIGH`.

### 5. Oznaczenie zadania jako wykonane

`PATCH /tasks/{task_uid}`

```json
{
  "is_done": true
}
```

### 6. Filtrowanie danych

```text
GET /subjects?user_uid=UUID_UŻYTKOWNIKA
GET /topics?subject_uid=UUID_PRZEDMIOTU
GET /tasks?topic_uid=UUID_TEMATU
```

## Kody odpowiedzi

- `200 OK` — poprawny odczyt lub aktualizacja,
- `201 Created` — poprawne utworzenie zasobu,
- `204 No Content` — poprawne usunięcie zasobu,
- `404 Not Found` — zasób nie istnieje,
- `409 Conflict` — konflikt danych, np. zajęty username lub email,
- `422 Unprocessable Entity` — dane nie przeszły walidacji Pydantic.

## Testy

Uruchom wszystkie testy:

```powershell
python -m pytest -q --basetemp=.test-tmp
```

Testy API korzystają z tymczasowej bazy SQLite i nadpisują zależność `get_db`,
dzięki czemu nie modyfikują danych w PostgreSQL. Zestaw sprawdza między innymi:

- endpoint `/health`,
- pełny przepływ użytkownik → przedmiot → temat → zadanie,
- tworzenie, pobieranie, edycję i usuwanie każdego głównego zasobu,
- odpowiedzi `404` dla nieistniejących UUID,
- odpowiedź `409` dla powtórzonego username,
- zmianę hasła bez ujawniania hasha w odpowiedzi.

## Archiwalna aplikacja konsolowa

Poprzednia wersja programu została zachowana w `legacy_cli/`. Jest odseparowana
od aktualnego API i używa pliku JSON zamiast PostgreSQL.

```powershell
python -m legacy_cli.main
```

Uruchomienie wersji legacy może utworzyć lokalny `data.json`, który jest
ignorowany przez Git.

## Znane ograniczenia

- API nie ma jeszcze logowania ani tokenów dostępu,
- listy nie mają jeszcze paginacji,
- `study_sessions` i `exam_results` są odwzorowane w bazie, ale nie mają routerów,
- projekt nie posiada jeszcze frontendu,
- testy integracyjne nie uruchamiają osobnej instancji PostgreSQL.

## Planowany rozwój

- uwierzytelnianie użytkowników i JWT,
- paginacja, sortowanie i bardziej rozbudowane filtrowanie,
- endpointy sesji nauki i wyników egzaminów,
- frontend webowy,
- moduł AI do generowania planów nauki i zadań,
- testy integracyjne z PostgreSQL.
