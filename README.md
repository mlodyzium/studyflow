# StudyFlow API

StudyFlow to backend aplikacji wspierającej organizację nauki. Pozwala zarządzać
użytkownikami, przedmiotami, tematami oraz zadaniami przez REST API. Projekt
korzysta z FastAPI, Pydantic, SQLAlchemy, PostgreSQL oraz Alembic.

API udostępnia pełny CRUD dla głównych zasobów, automatyczną dokumentację
Swagger, walidację danych i bezpieczne hashowanie haseł przy użyciu Argon2.

## Najważniejsze możliwości

- tworzenie, pobieranie, edycja i usuwanie użytkowników,
- rejestracja, logowanie JWT i izolacja danych użytkowników,
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
JWT_SECRET_KEY=wygeneruj-dlugi-losowy-sekret
ACCESS_TOKEN_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

Zamiast osobnych zmiennych możesz ustawić pełny adres połączenia:

```env
DATABASE_URL=postgresql+psycopg://postgres:twoje_haslo@localhost:5432/studyflow
```

Plik `.env` zawiera dane poufne i jest ignorowany przez Git. Do repozytorium
należy dodawać wyłącznie `.env.example` bez prawdziwego hasła.

## Docker Compose

Frontend znajduje się w katalogu `frontend/` i jest zbudowany w React,
TypeScript oraz Vite. W Compose jego produkcyjny build jest serwowany przez
Nginx, który przekazuje zapytania spod `/api` do FastAPI. Dzięki temu przeglądarka
korzysta z jednego adresu i nie wymaga dodatkowej konfiguracji CORS.

Projekt można uruchomić razem z PostgreSQL w kontenerach. Wymagany jest Docker
Desktop z obsługą polecenia `docker compose`.

Skopiuj przykładową konfigurację, jeżeli nie masz jeszcze `.env`:

```powershell
Copy-Item .env.example .env
```

Następnie zbuduj i uruchom cały zestaw:

```powershell
docker compose up --build
```

Compose uruchamia trzy usługi:

- `db` — PostgreSQL z trwałym wolumenem `postgres_data`,
- `api` — FastAPI uruchamiane przez Uvicorn,
- `frontend` — aplikację React serwowaną przez Nginx.

Kontener API czeka na prawidłowy healthcheck PostgreSQL, wykonuje
`alembic upgrade head`, a następnie uruchamia serwer. Domyślne adresy:

- aplikacja webowa: `http://localhost:5173`,
- Swagger: `http://localhost:8000/docs`,
- healthcheck API: `http://localhost:8000/health`,
- PostgreSQL z hosta: `localhost:5433`.

Porty można zmienić w `.env`:

```env
API_PORT=8000
POSTGRES_PORT=5433
FRONTEND_PORT=5173
```

Poziom logowania aplikacji można ustawić przez:

```env
LOG_LEVEL=INFO
```

Obsługiwane są standardowe poziomy Pythona, między innymi `DEBUG`, `INFO`,
`WARNING` i `ERROR`.

Przydatne polecenia:

```powershell
docker compose ps
docker compose logs -f api
docker compose stop
docker compose down
```

Każdy request poza healthcheckiem jest logowany z metodą HTTP, ścieżką,
statusem, czasem wykonania i `request_id`. Identyfikator jest zwracany w nagłówku
`X-Request-ID`. Możesz też przesłać własny `X-Request-ID`, co ułatwia śledzenie
jednego żądania pomiędzy frontendem i backendem. Body requestu oraz hasła nie są
logowane.

`docker compose down` usuwa kontenery i sieć, ale zachowuje dane PostgreSQL.
Polecenie poniżej usuwa również wolumen i wszystkie dane bazy kontenerowej:

```powershell
docker compose down -v
```

> Baza uruchomiona przez Compose jest oddzielna od PostgreSQL zainstalowanego
> bezpośrednio na komputerze. Dane są przechowywane w wolumenie Dockera.

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
| `POST` | `/auth/register` | Rejestracja użytkownika |
| `POST` | `/auth/login` | Logowanie i pobranie tokenu JWT |
| `GET` | `/users/me` | Dane zalogowanego użytkownika |
| `PATCH` | `/users/me` | Edycja własnego konta |
| `DELETE` | `/users/me` | Usunięcie własnego konta |
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
| `POST/GET` | `/study-sessions` | Tworzenie i lista sesji nauki |
| `GET/PATCH/DELETE` | `/study-sessions/{uid}` | CRUD pojedynczej sesji |
| `POST/GET` | `/exam-results` | Tworzenie i lista wyników egzaminów |
| `GET/PATCH/DELETE` | `/exam-results/{uid}` | CRUD pojedynczego wyniku |

## Przykładowy przepływ w Swaggerze

### 1. Utworzenie użytkownika

`POST /auth/register`

```json
{
  "username": "student",
  "password": "bezpieczne-haslo",
  "email": "student@example.com"
}
```

Hasło jest hashowane algorytmem Argon2. API nigdy nie zwraca hasła ani
`password_hash` w odpowiedzi.

Następnie zaloguj się przez `POST /auth/login` i skopiuj `access_token`.
W Swaggerze kliknij **Authorize** i podaj token. Wszystkie dalsze operacje są
ograniczone do danych zalogowanego użytkownika.

### 2. Utworzenie przedmiotu

`POST /subjects`

```json
{
  "name": "Matematyka",
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
GET /subjects?search=matematyka
GET /topics?subject_uid=UUID_PRZEDMIOTU
GET /tasks?topic_uid=UUID_TEMATU
```

## Paginacja

Endpointy listujące przedmioty, tematy, zadania, sesje i wyniki
przyjmują parametry `page` i `page_size`:

```text
GET /tasks?page=2&page_size=20
```

- `page` zaczyna się od `1`,
- domyślne `page_size` wynosi `20`,
- maksymalne `page_size` wynosi `100`,
- filtry można łączyć z paginacją.

Przykład:

```text
GET /tasks?topic_uid=UUID_TEMATU&page=1&page_size=10
```

Odpowiedź listy ma wspólny format:

```json
{
  "items": [],
  "page": 1,
  "page_size": 10,
  "total": 0,
  "pages": 0
}
```

Pole `total` określa liczbę wszystkich rekordów spełniających filtr, natomiast
`pages` informuje frontend, ile stron może wyświetlić.

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

Testy na prawdziwym, tymczasowym PostgreSQL uruchomisz w Dockerze:

```powershell
docker compose --profile test run --build --rm tests
docker compose stop db-test
```

## Archiwalna aplikacja konsolowa

Poprzednia wersja programu została zachowana w `legacy_cli/`. Jest odseparowana
od aktualnego API i używa pliku JSON zamiast PostgreSQL.

```powershell
python -m legacy_cli.main
```

Uruchomienie wersji legacy może utworzyć lokalny `data.json`, który jest
ignorowany przez Git.

## Znane ograniczenia

- projekt nie posiada jeszcze frontendu,
- tokeny JWT nie mają jeszcze mechanizmu odświeżania ani unieważniania.

## Planowany rozwój

- sortowanie i bardziej rozbudowane filtrowanie,
- frontend webowy,
- moduł AI do generowania planów nauki i zadań,
- testy integracyjne z PostgreSQL.
