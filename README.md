# StudyFlow

StudyFlow to kompletna aplikacja webowa do organizowania nauki. Łączy planowanie przedmiotów, tematów i zadań z rejestrowaniem sesji, kalendarzem oraz Asystentem AI opartym na Google Gemini.

Projekt zawiera responsywny frontend React, REST API w FastAPI, bazę PostgreSQL, uwierzytelnianie JWT, migracje Alembic, testy automatyczne oraz gotową konfigurację Docker Compose.

## Najważniejsze funkcje

### Organizacja nauki

- rejestracja, logowanie, edycja profilu i lokalne zdjęcie profilowe,
- izolacja danych pomiędzy użytkownikami,
- przedmioty z datą egzaminu, własnym kolorem i tagami; zakończone można archiwizować,
- tematy przypisane do przedmiotów,
- zadania z terminem, priorytetem, statusem i prywatną notatką,
- filtrowanie zadań po przedmiocie, temacie, statusie, priorytecie i terminie; zbiorcze kończenie i duplikowanie,
- sesje nauki z własnym tytułem, czasem, notatką i powiązaniem z wybranym zasobem,
- generator AI, który z kilku słów tworzy tytuł i uporządkowaną notatkę z sesji,
- historia sesji i licznik kolejnych dni nauki,
- kalendarz z egzaminami, zadaniami i dniami planów, przeciąganiem zadań oraz eksportem iCalendar (`.ics`),
- bezpośrednie dodawanie pojedynczych wydarzeń do Google Calendar,
- dashboard z planem na dziś, zaległymi zadaniami, egzaminami i powtórkami,
- kreator pierwszego planu nauki, osobny czas i opcjonalna godzina dla każdego dnia oraz konfigurowalny skrót do nowego zadania,
- jasny i ciemny motyw,
- pięć gotowych kolorów interfejsu oraz możliwość wybrania własnego koloru z palety,
- płynne przejścia pomiędzy motywami i zapamiętywanie ustawień w przeglądarce,
- animowany, jedenastokrokowy samouczek uruchamiany po rejestracji i dostępny później z menu konta,
- responsywny interfejs desktopowy i mobilny.

### Asystent AI

Asystent wykorzystuje Gemini i oferuje dwa tryby:

- **Notatka** — podsumowanie, sekcje tematyczne, najważniejsze punkty i pytania kontrolne.
- **Plan nauki** — harmonogram rozłożony na dni, z celami, aktywnościami i czasem pracy.

Przed generowaniem użytkownik wybiera rodzaj materiału i przedmiot. Pola tematu oraz zadania działają jako „wybierz albo wpisz”: można wskazać istniejący element lub wpisać nowy. Nowa nazwa tematu tworzy temat automatycznie. Generowanie notatki może utworzyć zadanie z krótkim tytułem dobranym przez AI; sam plan ma oddzielne dni bez dodatkowego zadania. Dla notatki można ustawić poziom szczegółowości, a dla planu liczbę dni i czas nauki dziennie.

Zapytanie do Gemini jest wysyłane dopiero po kliknięciu przycisku generowania. Każdy poprawny wynik jest zapisywany w PostgreSQL i dostępny później przez **Historia materiałów** na dashboardzie. Przy błędzie formularz zachowuje wpisane dane, pozwala ponowić próbę, zapisać własną notatkę lub utworzyć prosty plan bez AI.

Notatki można pobrać jako Markdown albo otworzyć widok wydruku i zapisać jako PDF. Każda nowa notatka trafia też do kolejki powtórek. Plan ma osobne dni z postępem; można je kończyć, przesuwać, duplikować i poprawiać pojedynczo. Dni planu są widoczne w kalendarzu, a osobne zadania kalendarzowe tworzy się na życzenie.

Przy planie liczba minut dziennie jest orientacyjna: aplikacja zachowuje łączny czas nauki i może inaczej rozłożyć go pomiędzy dni. Jeśli sprawdzian wypada wcześniej niż koniec wybranego planu, wcześniejsze dni stają się dłuższe, a w dniu sprawdzianu pozostaje tylko powtórka do 15 minut. Gdy czasu nie da się realnie zmieścić przed sprawdzianem, aplikacja wyjaśnia konflikt zamiast zapisać skrócony plan.

Materiały są również wiązane z zadaniami:

- wygenerowana notatka pojawia się w czytelnej sekcji **Materiały AI** w szczegółach zadania,
- plan nauki pojawia się w tej samej sekcji jako rozwijany materiał, jeśli był powiązany z zadaniem,
- szczegóły zadania pokazują oddzielnie notatki ze wszystkich powiązanych sesji nauki,
- prośba o sam plan nie tworzy automatycznie zadań; użytkownik może utworzyć je później przyciskiem przy planie.

Backend AI:

- nie udostępnia klucza Gemini przeglądarce,
- wymusza odpowiedzi JSON i waliduje je przez Pydantic,
- obsługuje timeouty i chwilowe przeciążenie API,
- ponawia wybrane zapytania i korzysta z modelu awaryjnego,
- weryfikuje własność tematu oraz zadania,
- zapisuje wyniki oddzielnie dla każdego użytkownika.

### T3ACH — agent nauki

T3ACH jest konwersacyjną warstwą nad StudyFlow. Użytkownik opisuje naturalnym językiem cel, np. „za dwa tygodnie mam sprawdzian z funkcji kwadratowej”, a agent:

- uwzględnia istniejące przedmioty i tematy użytkownika,
- w razie braku kluczowych informacji zadaje jedno pytanie doprecyzowujące,
- proponuje przedmiot, temat oraz od 1 do 6 konkretnych zadań,
- dobiera priorytety i opcjonalne terminy,
- pokazuje cały plan przed wykonaniem,
- zapisuje dane dopiero po kliknięciu **Zatwierdź i zapisz w StudyFlow**.

Generowanie propozycji i jej wykonanie są rozdzielone na dwa endpointy. Backend zapisuje propozycję i zatwierdza ją po identyfikatorze; sprawdza właściciela oraz blokuje ponowne wykonanie. Dotychczasowe generatory notatek i planów pozostają dostępne bezpośrednio z panelu T3ACH.

T3ACH najpierw przygotowuje odpowiedź tekstową, a potem czyta ją głosem AI. Jeśli usługa głosu jest niedostępna, pokazuje osobny komunikat i przełącza odczyt na polski głos dostępny w przeglądarce lub na urządzeniu. Odpowiedź tekstowa pozostaje widoczna.

### AI w sesjach nauki

Podczas dodawania lub edycji sesji można wpisać krótki opis wykonanej pracy, np. `10 zadań z równań i powtórka wzorów`. Przycisk **Utwórz tytuł i notatkę z AI** wysyła opis do API, a Gemini zwraca:

- krótki i czytelny tytuł sesji,
- uporządkowaną notatkę opisującą wykonaną pracę,
- ewentualną sugestię kolejnego kroku, wyłącznie jeśli wynika z opisu.

Wynik można poprawić przed zapisaniem. Sesje są widoczne w historii, szczegółach sesji oraz na kaflu **Sesje tego zadania**. Można je edytować i usuwać z potwierdzeniem.

## Motywy i personalizacja

StudyFlow rozdziela tryb jasny/ciemny od koloru przewodniego. Użytkownik może niezależnie wybrać:

- tryb jasny albo ciemny,
- limonkowy, fioletowy, różowy, niebieski lub grafitowy wariant,
- dowolny własny kolor z systemowej palety barw.

Wybrany kolor obejmuje cały interfejs: dashboard, przyciski, formularze, filtry, kalendarz, sesje, strony szczegółów, materiały AI, obramowania, poświaty i gradient podążający za kursorem. Aplikacja automatycznie wylicza jaśniejsze tła oraz kontrastowe kolory tekstu. Zmiana jest animowana, a ustawienia są przechowywane w `localStorage`.

Przełącznik jasnego i ciemnego wariantu oraz paleta kolorów są widoczne na lewym pasku, nad profilem.

## Konto i ustawienia użytkownika

Kliknięcie profilu na dole lewego paska otwiera menu z osobnymi oknami **Ustawienia konta** i **Ustawienia użytkownika**. W pierwszym można:

- edytować nazwę użytkownika, adres e-mail i hasło,
- wgrać, zmienić albo usunąć zdjęcie profilowe.

W ustawieniach użytkownika można wybrać strefę czasową z listy, sugerowany czas nauki na dzień oraz osobne skróty klawiszowe do nowego zadania i Asystenta AI. Menu profilu pozwala także ponownie uruchomić samouczek.

Zdjęcie profilowe może mieć maksymalnie 2 MB. Jest zapisywane w pamięci lokalnej przeglądarki osobno dla identyfikatora konta — nie trafia do API ani PostgreSQL i nie synchronizuje się pomiędzy urządzeniami. Jeśli zdjęcie nie zostało ustawione, aplikacja pokazuje inicjały użytkownika.

## Samouczek pierwszego logowania

Po rejestracji i pierwszym zalogowaniu uruchamia się interaktywny samouczek. W jedenastu krokach pokazuje dashboard, przedmioty, tematy, zadania, sesje, kalendarz, szybki zapis nauki, Asystenta AI, motyw oraz menu konta. Po nim kreator pozwala ustawić własny skrót, dodać pierwszy przedmiot i przygotować materiał. Można cofać kroki lub pominąć samouczek.

Samouczek nie uruchamia się automatycznie podczas zwykłego logowania. Aby wrócić do niego później, kliknij profil z zębatką na lewym pasku i wybierz **Uruchom samouczek**.

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

### HTTPS na innym urządzeniu w sieci lokalnej

W `.env` wpisz adres IP komputera, na którym działa Docker, np. `LAN_HOST=192.168.1.100`. Następnie uruchom profil LAN:

```sh
docker compose --profile lan up -d --build
mkdir -p .local
docker compose cp lan-https:/data/caddy/pki/authorities/local/root.crt .local/studyflow-lan-ca.crt
```

Na telefonie lub drugim komputerze połączonym z tą samą siecią otwórz `https://192.168.1.100:8443` (podstaw adres z `LAN_HOST`). Serwer Caddy używa lokalnego urzędu certyfikacji. Aby przeglądarka uznała połączenie za bezpieczne i udostępniła mikrofon, zaimportuj plik `.local/studyflow-lan-ca.crt` na drugim urządzeniu jako zaufany certyfikat główny. Samo wejście na stronę mimo ostrzeżenia o certyfikacie może nie wystarczyć dla mikrofonu. Na iOS po instalacji profilu włącz pełne zaufanie w ustawieniach certyfikatów; na Androidzie zaimportuj certyfikat CA w ustawieniach zabezpieczeń. Aplikacja może też zapytać o uprawnienie do mikrofonu.

Zwykły HTTP, API i PostgreSQL są dostępne tylko przez `localhost` komputera z Dockerem. Jeśli adres IP komputera się zmieni, popraw `LAN_HOST` i uruchom ponownie `lan-https`. Plik `.local/` jest ignorowany przez Git; nie publikuj kluczy prywatnych z wolumenu Caddy.

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
| `LAN_HOST` | `localhost` | Adres IP komputera w sieci lokalnej dla HTTPS |
| `LAN_HTTPS_PORT` | `8443` | Port HTTPS w sieci lokalnej |
| `GEMINI_API_KEY` | brak | Prywatny klucz Gemini |
| `GEMINI_MODEL` | `gemini-flash-lite-latest` | Główny model AI |
| `GEMINI_FALLBACK_MODEL` | `gemini-flash-latest` | Model awaryjny |
| `AI_RATE_LIMIT_PER_DAY` | `300` | Dzienny limit generowania na konto |
| `TTS_RATE_LIMIT_PER_DAY` | `500` | Dzienny limit mowy na konto |
| `LOGIN_RATE_LIMIT_PER_15_MIN` | `240` | Dodatkowy limit wszystkich prób logowania na nazwę konta |
| `FAILED_LOGIN_LIMIT` | `20` | Liczba błędnych haseł w 15 minut przed blokadą |
| `LOGIN_LOCK_MINUTES` | `15` | Czas automatycznej blokady konta |
| `REGISTRATION_RATE_LIMIT_PER_DAY` | `40` | Limit rejestracji na adres IP |
| `METRICS_TOKEN` | pusty | Sekret do `/internal/metrics`; pusty wyłącza endpoint |

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
6. Zapisuj sesje nauki ręcznie lub wygeneruj ich tytuł i notatkę z krótkiego opisu przez AI.
7. Na lewym pasku wybierz jasny/ciemny tryb.
8. Kolor interfejsu zmienisz nad profilem; kliknij profil z zębatką, aby ustawić zdjęcie albo ponownie uruchomić samouczek.

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
3. Wybierz istniejący temat z podpowiedzi albo wpisz nazwę nowego.
4. Wybierz zapisane zadanie lub wpisz własny cel, np. „Powtórka definicji do kartkówki”.
5. Wybierz długość: krótką, standardową lub szczegółową.
6. Kliknij **Generuj notatkę**.

Po wygenerowaniu treść zostanie zapisana i pokazana w sekcji **Materiały AI** w szczegółach wybranego zadania. Jeśli temat lub zadanie nie zostały wcześniej utworzone, aplikacja utworzy brakujące elementy i użyje tytułu zadania wygenerowanego przez AI.

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
│   ├── src/accents.css      # pełny system motywów kolorystycznych
│   ├── src/task-details.css # rozszerzone szczegóły zadań i sesji
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
- `20260908_03` — historia materiałów AI,
- `20260911_04` — tytuły sesji nauki,
- `20260913_05` — historia rozmów T3ACH,
- `20260929_06` — plany, powtórki i preferencje,
- `20260929_07` — czasowa blokada logowania,
- `20260929_08` — godzina i czas trwania każdego dnia planu,
- `20260929_09` — skrót klawiszowy Asystenta AI.

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
| `POST` | `/ai/session-note` | Generowanie tytułu i notatki sesji z krótkiego opisu |
| `POST` | `/ai/t3ach/propose` | Interpretacja celu i przygotowanie propozycji działań |
| `POST` | `/ai/t3ach/execute` | Zapis zatwierdzonej propozycji T3ACH |
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

### Przykład notatki z sesji AI

```json
POST /ai/session-note

{
  "language": "polski",
  "description": "Rozwiązałem 10 zadań z równań i powtórzyłem wzory"
}
```

Endpoint zwraca krótki `title` oraz gotowe `notes`. Sam zapis sesji następuje przez `POST /study-sessions`, dzięki czemu użytkownik może wcześniej poprawić wygenerowaną treść.

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

Aktualna rewizja powinna wynosić `20260929_09`.

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
- przy publicznym wdrożeniu dodaj trwały, współdzielony licznik limitów oraz kontrolę kosztów AI,
- traktuj materiały AI jako pomoc, a nie gwarantowane źródło wiedzy.

Projekt portfolio nie ma jeszcze refresh tokenów, unieważniania sesji ani panelu administratora. Po 20 błędnych hasłach w ciągu 15 minut konto blokuje się na 15 minut; blokada jest zapisana w bazie i wygasa automatycznie. Poprawne logowanie zeruje licznik błędów. Dodatkowe limity wszystkich żądań są trzymane w pamięci procesu API i zerują się po restarcie. `/health/ready` sprawdza bazę oraz aktualność migracji, a `/internal/metrics` udostępnia liczniki po ustawieniu sekretu.

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
- wyszukiwanie w historii AI,
- streaming odpowiedzi,
- współdzielone limity oraz bardziej szczegółowe statystyki użycia,
- refresh tokeny,
- testy end-to-end frontendu.

## Licencja

Projekt został przygotowany jako aplikacja edukacyjna i portfolio. Przed wykorzystaniem w innym projekcie dodaj odpowiedni plik licencji i zasady użycia.
