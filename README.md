# StudyFlow

StudyFlow to kompletna aplikacja webowa do organizowania nauki. Łączy planowanie przedmiotów, tematów i zadań z rejestrowaniem sesji, kalendarzem oraz Asystentem AI opartym na Google Gemini.

Projekt zawiera responsywny frontend React, REST API w FastAPI, bazę PostgreSQL, uwierzytelnianie JWT, migracje Alembic, testy automatyczne oraz gotową konfigurację Docker Compose.

## Najważniejsze funkcje

### Organizacja nauki

- rejestracja, logowanie i edycja profilu,
- izolacja danych pomiędzy użytkownikami,
- przedmioty z opcjonalną datą egzaminu,
- tematy przypisane do przedmiotów,
- zadania z terminem, priorytetem, statusem i prywatną notatką,
- filtrowanie zadań po przedmiocie, temacie, statusie i priorytecie,
- sesje nauki z czasem, notatką i powiązaniem z wybranym zasobem,
- historia sesji i licznik kolejnych dni nauki,
- kalendarz z egzaminami oraz terminami zadań,
- dashboard z postępem, najbliższymi zadaniami i aktywnymi przedmiotami,
- jasny i ciemny motyw,
- responsywny interfejs desktopowy i mobilny.

### Asystent AI

Asystent wykorzystuje Gemini i oferuje dwa tryby:

- **Notatka** — podsumowanie, sekcje tematyczne, najważniejsze punkty i pytania kontrolne.
- **Plan nauki** — harmonogram rozłożony na dni, z celami, aktywnościami i czasem pracy.

Przed generowaniem użytkownik wybiera rodzaj materiału, przedmiot, temat oraz opcjonalnie istniejące zadanie albo własny cel. Dla notatki można ustawić poziom szczegółowości, a dla planu liczbę dni i czas nauki dziennie.

Zapytanie do Gemini jest wysyłane dopiero po kliknięciu przycisku generowania. Każdy poprawny wynik jest automatycznie zapisywany w PostgreSQL i dostępny później przez **Historia materiałów** na dashboardzie.

Materiały są również wiązane z zadaniami:

- wygenerowana notatka trafia bezpośrednio do pola notatki wybranego zadania,
- plan nauki pojawia się jako osobny kafel w szczegółach zadania,
- jeśli użytkownik nie wybierze istniejącego zadania, StudyFlow automatycznie tworzy nowe zadanie z krótkim tytułem zaproponowanym przez AI.

Backend AI:

- nie udostępnia klucza Gemini przeglądarce,
- wymusza odpowiedzi JSON i waliduje je przez Pydantic,
- obsługuje timeouty i chwilowe przeciążenie API,
- ponawia wybrane zapytania i korzysta z modelu awaryjnego,
- weryfikuje własność tematu oraz zadania,
- zapisuje wyniki oddzielnie dla każdego użytkownika.

## Technologie

| Warstwa | Technologie |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, Lucide React |
| Serwer frontendu | Nginx |
| Backend | Python 3.13, FastAPI, Uvicorn, Pydantic |
| Baza | PostgreSQL 17, SQLAlchemy 2, Psycopg 3 |
| Migracje | Alembic |
| Bezpieczeństwo | JWT, pwdlib, Argon2 |
| AI | Google Gemini Generate Content API |
| Testy | pytest, FastAPI TestClient, HTTPX |
| Kontenery | Docker, Docker Compose |

## Szybki start z Docker Compose

To rekomendowany sposób uruchomienia. Nie wymaga lokalnej instalacji Node.js, PostgreSQL ani pakietów Pythona.

### Wymagania

- Git,
- Docker Desktop z poleceniem `docker compose`,
- klucz Gemini API do korzystania z funkcji AI.

### 1. Pobierz projekt

```powershell
git clone https://github.com/mlodyzium/studyflow.git
cd studyflow
```

### 2. Utwórz konfigurację

```powershell
Copy-Item .env.example .env
```

W `.env` ustaw co najmniej:

```env
DB_PASSWORD=zmien-to-haslo
JWT_SECRET_KEY=wygeneruj-dlugi-losowy-sekret
GEMINI_API_KEY=twoj_prawdziwy_klucz
```

Klucz Gemini można utworzyć w Google AI Studio. Aplikacja działa bez niego, ale generatory AI będą niedostępne.

### 3. Uruchom system

```powershell
docker compose up --build
```

Uruchomienie w tle:

```powershell
docker compose up -d --build
```

Domyślne adresy:

- aplikacja: http://localhost:5173,
- Swagger UI: http://localhost:8000/docs,
- ReDoc: http://localhost:8000/redoc,
- API healthcheck: http://localhost:8000/health,
- PostgreSQL z hosta: `localhost:5433`.

Compose uruchamia:

- `db` — PostgreSQL z trwałym wolumenem `postgres_data`,
- `api` — FastAPI uruchamiane przez Uvicorn,
- `frontend` — produkcyjny build React serwowany przez Nginx.

API czeka na bazę, automatycznie wykonuje `alembic upgrade head`, a następnie startuje. Nginx obsługuje SPA i przekazuje `/api/*` do FastAPI.

Zatrzymanie:

```powershell
docker compose down
```

To zachowuje dane. Aby usunąć również wolumen i całą bazę:

```powershell
docker compose down -v
```

> `down -v` nieodwracalnie usuwa konta, przedmioty, zadania, sesje i historię AI z bazy kontenerowej.

## Konfiguracja `.env`

| Zmienna | Wartość domyślna | Znaczenie |
| --- | --- | --- |
| `APP_NAME` | `StudyFlow API` | Nazwa w OpenAPI |
| `LOG_LEVEL` | `INFO` | Poziom logowania |
| `JWT_SECRET_KEY` | sekret deweloperski | Klucz podpisujący JWT; zmień go poza lokalnym demo |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Ważność tokenu |
| `CORS_ORIGINS` | localhost 3000 i 5173 | Originy oddzielone przecinkami |
| `DB_USER` | `postgres` | Użytkownik PostgreSQL |
| `DB_PASSWORD` | zależna od konfiguracji | Hasło PostgreSQL |
| `DB_HOST` | `localhost` | Host bazy lokalnej; Compose używa `db` |
| `DB_PORT` | `5432` | Wewnętrzny port PostgreSQL |
| `DB_NAME` | `studyflow` | Nazwa bazy |
| `DATABASE_URL` | składany z `DB_*` | Opcjonalny pełny URL SQLAlchemy |
| `API_PORT` | `8000` | Port API na hoście |
| `FRONTEND_PORT` | `5173` | Port aplikacji |
| `POSTGRES_PORT` | `5433` | Port bazy na hoście |
| `GEMINI_API_KEY` | brak | Prywatny klucz Gemini |
| `GEMINI_MODEL` | `gemini-flash-lite-latest` | Główny model AI |
| `GEMINI_FALLBACK_MODEL` | `gemini-flash-latest` | Model awaryjny |

Przykład:

```env
APP_NAME=StudyFlow API
LOG_LEVEL=INFO
JWT_SECRET_KEY=replace-with-a-long-random-secret
ACCESS_TOKEN_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

DB_USER=postgres
DB_PASSWORD=twoje_haslo
DB_HOST=localhost
DB_PORT=5432
DB_NAME=studyflow

API_PORT=8000
POSTGRES_PORT=5433
FRONTEND_PORT=5173

GEMINI_API_KEY=twoj_klucz_gemini
GEMINI_MODEL=gemini-flash-lite-latest
GEMINI_FALLBACK_MODEL=gemini-flash-latest
```

Alternatywny pełny adres bazy:

```env
DATABASE_URL=postgresql+psycopg://postgres:twoje_haslo@localhost:5432/studyflow
```

Plik `.env` zawiera sekrety, jest ignorowany przez Git i nie powinien być publikowany. Klucza Gemini nie należy umieszczać w zmiennych `VITE_*`, ponieważ trafiają do kodu przeglądarki.

## Pierwsze użycie

1. Otwórz http://localhost:5173.
2. Utwórz konto i zaloguj się.
3. Dodaj przedmiot, np. „Matematyka”.
4. Dodaj temat, np. „Równania kwadratowe”.
5. Dodaj zadanie lub otwórz Asystenta AI.
6. Zapisuj sesje nauki, aby dashboard liczył czas i serię dni.

Hierarchia danych:

```text
User
├── Subject
│   ├── Topic
│   │   ├── Task
│   │   └── AI Material
│   ├── Study Session
│   └── Exam Result
└── AI Material History
```

## Jak korzystać z Asystenta AI

Asystenta można otworzyć z kafla na dashboardzie lub przyciskiem w prawym dolnym rogu.

### Notatka

1. Wybierz **Notatka**.
2. Wybierz przedmiot i temat.
3. Opcjonalnie wskaż zadanie zapisane wcześniej w StudyFlow — wynik skupi się na jego celu.
4. Jeżeli nie wybierasz zapisanego zadania, wpisz własny cel, np. „Powtórka definicji do kartkówki”.
5. Wybierz długość: krótką, standardową lub szczegółową.
6. Kliknij **Generuj notatkę**.

Po wygenerowaniu treść zostanie dopisana do szczegółów wybranego zadania. Jeśli zadanie nie zostało wybrane, aplikacja utworzy nowe w wybranym temacie i użyje tytułu wygenerowanego przez AI.

### Plan nauki

1. Wybierz **Plan nauki**.
2. Wybierz przedmiot i temat.
3. Wskaż istniejące zadanie albo wpisz własny cel.
4. Ustaw liczbę dni od `1` do `30`.
5. Ustaw dzienny czas od `10` do `240` minut.
6. Kliknij **Ułóż plan**.

Plan zostanie przypięty do wybranego zadania i będzie widoczny jako rozwijany kafel w jego szczegółach. Bez wybranego zadania aplikacja utworzy nowe zadanie i przypisze do niego plan.

### Historia materiałów

Każdy udany wynik zapisuje się automatycznie. Na dashboardzie kliknij **Historia materiałów**, a następnie wybierz notatkę lub plan z listy. API zwraca do 50 ostatnich materiałów zalogowanego użytkownika.

Materiały wygenerowane przed dodaniem historii nie pojawią się na liście. Usunięcie tematu usuwa również jego materiały. Usunięcie zadania pozostawia materiał, ale czyści opcjonalne powiązanie z tym zadaniem.

> AI może popełniać błędy. Ważne informacje warto sprawdzić w podręczniku, materiałach prowadzącego lub wiarygodnym źródle.

## Architektura

```text
Przeglądarka
    │
    ▼
React + TypeScript
    │ /api/*
    ▼
Nginx reverse proxy
    │
    ▼
FastAPI routers
    ├── Pydantic — walidacja
    ├── Services — logika i Gemini API
    └── SQLAlchemy
            │
            ▼
        PostgreSQL
```

Klucz Gemini istnieje wyłącznie po stronie API. Frontend przekazuje identyfikatory i parametry, backend pobiera bezpieczny kontekst z bazy, wywołuje Gemini, waliduje odpowiedź i zapisuje wynik.

## Struktura projektu

```text
studyflow/
├── alembic/versions/       # migracje bazy
├── app/
│   ├── core/               # konfiguracja, logging i bezpieczeństwo
│   ├── db/                 # engine i sesje SQLAlchemy
│   ├── dependencies/       # zależności FastAPI
│   ├── models/             # modele bazy
│   ├── routers/            # endpointy HTTP
│   ├── schemas/            # modele Pydantic
│   ├── services/           # logika CRUD i Gemini
│   └── main.py
├── docker/entrypoint.sh    # migracje i start API
├── frontend/
│   ├── src/App.tsx
│   ├── src/api.ts
│   ├── src/types.ts
│   ├── src/styles.css
│   ├── Dockerfile
│   └── nginx.conf
├── legacy_cli/             # archiwalna wersja konsolowa
├── tests/
├── .env.example
├── compose.yaml
├── Dockerfile
└── requirements.txt
```

## Uruchomienie bez Dockera

### Backend

Wymagane są Python 3.11+ i działający PostgreSQL.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

API będzie dostępne pod http://127.0.0.1:8000.

### Frontend

Wymagany jest Node.js 22+.

```powershell
cd frontend
npm install
npm run dev
```

Build produkcyjny:

```powershell
npm run build
```

Poza Compose można wskazać API:

```env
VITE_API_URL=http://localhost:8000
```

W Compose frontend używa `/api`, a Nginx przekazuje ruch do usługi `api`.

## Migracje

Aktualny łańcuch:

- `20260907_01` — podstawowe tabele,
- `20260907_02` — notatki zadań i kontekst sesji,
- `20260908_03` — historia materiałów AI.

Polecenia:

```powershell
alembic current
alembic history
alembic upgrade head
alembic downgrade -1
alembic revision --autogenerate -m "opis zmiany"
```

Przed zastosowaniem przeczytaj wygenerowaną migrację. W Compose `upgrade head` wykonuje się automatycznie przy starcie API.

## API i autoryzacja

Poza `/health`, `/auth/register` i `/auth/login` endpointy wymagają JWT:

```http
Authorization: Bearer <access_token>
```

W Swaggerze kliknij **Authorize** i podaj token z `/auth/login`.

| Metoda | Endpoint | Opis |
| --- | --- | --- |
| `GET` | `/health` | Stan API |
| `POST` | `/auth/register` | Rejestracja |
| `POST` | `/auth/login` | Logowanie |
| `GET/PATCH/DELETE` | `/users/me` | Własne konto |
| `POST/GET` | `/subjects` | Tworzenie i lista przedmiotów |
| `GET/PATCH/DELETE` | `/subjects/{uid}` | Operacje na przedmiocie |
| `POST/GET` | `/topics` | Tworzenie i lista tematów |
| `GET/PATCH/DELETE` | `/topics/{uid}` | Operacje na temacie |
| `POST/GET` | `/tasks` | Tworzenie i lista zadań |
| `GET/PATCH/DELETE` | `/tasks/{uid}` | Operacje na zadaniu |
| `POST/GET` | `/study-sessions` | Tworzenie i lista sesji |
| `GET/PATCH/DELETE` | `/study-sessions/{uid}` | Operacje na sesji |
| `POST/GET` | `/exam-results` | Tworzenie i lista wyników |
| `GET/PATCH/DELETE` | `/exam-results/{uid}` | Operacje na wyniku |
| `POST` | `/ai/topics/{topic_uid}/notes` | Generowanie i zapis notatki |
| `POST` | `/ai/topics/{topic_uid}/plan` | Generowanie i zapis planu |
| `GET` | `/ai/materials` | Historia materiałów użytkownika |

Pełny kontrakt jest dostępny w Swagger UI.

### Przykład notatki AI

```json
POST /ai/topics/UUID_TEMATU/notes

{
  "language": "polski",
  "detail_level": "standard",
  "task_uid": "UUID_ZADANIA_LUB_NULL",
  "custom_goal": null
}
```

`detail_level`: `short`, `standard` albo `detailed`.

### Przykład planu AI

```json
POST /ai/topics/UUID_TEMATU/plan

{
  "language": "polski",
  "days": 7,
  "minutes_per_day": 45,
  "task_uid": null,
  "custom_goal": "Przygotowanie do sprawdzianu"
}
```

Jeżeli `task_uid` nie należy do tematu z adresu, API zwróci `422`.

## Paginacja i filtrowanie

Standardowa lista:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "pages": 0
}
```

Strony zaczynają się od `1`, a maksymalne `page_size` to `100`.

```text
GET /subjects?search=matematyka&page=1&page_size=20
GET /topics?subject_uid=UUID&difficulty=Średni
GET /tasks?topic_uid=UUID&priority=HIGH&is_done=false
GET /tasks?search=kartkówka&sort=deadline&order=asc
```

## Statusy HTTP

| Status | Znaczenie |
| --- | --- |
| `200` | Poprawny odczyt lub aktualizacja |
| `201` | Utworzenie zasobu |
| `204` | Usunięcie |
| `401` | Brak lub nieważny token |
| `404` | Brak zasobu albo brak dostępu |
| `409` | Konflikt danych |
| `422` | Niepoprawne dane wejściowe |
| `502` | Gemini nie zwróciło poprawnego materiału |
| `503` | Integracja AI nie jest skonfigurowana |

## Testy

Lokalnie:

```powershell
python -m pytest tests -q --basetemp=.test-tmp
```

Bez `TEST_DATABASE_URL` używana jest izolowana SQLite w pamięci. Gemini jest mockowane, więc testy nie zużywają limitu i nie wymagają klucza.

Zakres obejmuje autoryzację, izolację danych, CRUD, filtry, paginację, walidację AI, przekazywanie kontekstu zadania i automatyczny zapis materiałów.

Na PostgreSQL w Dockerze:

```powershell
docker compose --profile test run --build --rm tests
docker compose stop db-test
```

## Przydatne polecenia

```powershell
docker compose ps
docker compose logs -f
docker compose logs -f api
docker compose restart

docker compose build frontend
docker compose up -d --force-recreate frontend

docker compose build api
docker compose up -d --force-recreate api

docker compose exec api alembic current
```

## Logging

Każde żądanie HTTP jest logowane z metodą, ścieżką, statusem, czasem i `request_id`. Identyfikator wraca w nagłówku `X-Request-ID`; klient może przesłać własny. Body, hasła i klucz Gemini nie są logowane.

```env
LOG_LEVEL=DEBUG
```

## Rozwiązywanie problemów

### Nie widzę zmian

```powershell
docker compose build frontend
docker compose up -d --force-recreate frontend
```

Następnie użyj `Ctrl + F5`.

### AI nie jest skonfigurowane

Ustaw `GEMINI_API_KEY` w `.env` i odtwórz API:

```powershell
docker compose up -d --force-recreate api
```

### Błąd generowania `502`

```powershell
docker compose logs api --tail 200
```

Możliwe przyczyny: limit API, przeciążenie `429/503`, timeout, niedostępny model lub odpowiedź niezgodna ze schematem. Aplikacja ma retry i model awaryjny, ale długotrwałych problemów po stronie dostawcy nie da się całkowicie ukryć.

### API nie startuje

```powershell
docker compose logs api
docker compose exec api alembic current
```

Aktualna rewizja powinna wynosić `20260908_03`.

### Port jest zajęty

```env
FRONTEND_PORT=5174
API_PORT=8001
POSTGRES_PORT=5434
```

### Frontend jest `unhealthy`

```powershell
docker compose logs frontend
docker inspect studyflow-frontend-1
```

Healthcheck odpytuje Nginx pod `http://127.0.0.1/` wewnątrz kontenera.

## Bezpieczeństwo i ograniczenia

- nie commituj `.env`,
- nie umieszczaj klucza Gemini w frontendzie,
- użyj losowego `JWT_SECRET_KEY` i silnego hasła PostgreSQL,
- ogranicz `CORS_ORIGINS` do własnej domeny,
- przed publicznym wdrożeniem skonfiguruj HTTPS,
- przed publicznym demo dodaj rate limiting i limit kosztów AI,
- traktuj materiały AI jako pomoc, a nie gwarantowane źródło wiedzy.

Projekt portfolio nie ma jeszcze refresh tokenów, unieważniania sesji, rate limitingu ani panelu administratora.

## Legacy CLI

Archiwalna wersja konsolowa znajduje się w `legacy_cli/`:

```powershell
python -m legacy_cli.main
```

Używa pliku JSON zamiast PostgreSQL i jest oddzielona od aplikacji webowej.

## Plan rozwoju

- głosowy asystent w stylu „Jarvisa”,
- chatbot korzystający z kontekstu postępów użytkownika,
- quizy, fiszki i zadania generowane przez AI,
- zapis planu AI bezpośrednio jako zadania w kalendarzu,
- wyszukiwanie i usuwanie historii AI,
- streaming odpowiedzi,
- rate limiting i statystyki użycia,
- refresh tokeny,
- testy end-to-end frontendu.

## Licencja

Projekt został przygotowany jako aplikacja edukacyjna i portfolio. Przed wykorzystaniem w innym projekcie dodaj odpowiedni plik licencji i zasady użycia.
