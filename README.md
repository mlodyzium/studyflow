# StudyFlow API

Backend do zarzadzania nauka zbudowany w FastAPI, SQLAlchemy i Pydantic.
Korzysta z wczesniejszej bazy PostgreSQL.

## Uruchomienie

Skopiuj `.env.example` do `.env` i wpisz dane swojej bazy PostgreSQL:

```text
DB_USER=postgres
DB_PASSWORD=twoje_haslo
DB_HOST=localhost
DB_PORT=5432
DB_NAME=studyflow
```

Nastepnie uruchom:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Dokumentacja Swagger: `http://127.0.0.1:8000/docs`

API korzysta z istniejacych tabel i mapuje starsze kolumny `nazwa` oraz `status`.
Nie wykonuje `drop_all`, wiec nie usuwa danych. Zmiany schematu powinny byc
prowadzone przez migracje Alembic.

## Migracje Alembic

Dla nowej, pustej bazy utworz schemat poleceniem:

```powershell
alembic upgrade head
```

Jesli Twoja dotychczasowa baza ma juz wszystkie tabele zgodne z migracja
poczatkowa, oznacz ja jako aktualna bez ponownego tworzenia tabel:

```powershell
alembic stamp head
```

Przed `stamp` porownaj istniejacy schemat z migracja. Kolejne zmiany modeli:

```powershell
alembic revision --autogenerate -m "opis zmiany"
alembic upgrade head
```

Kod jest podzielony na `models`, `schemas`, `services`, `routers`, `db` i `core`.

Kazdy zasob obsluguje pelny CRUD:

- `POST /users`, `GET /users`, `GET/PATCH/DELETE /users/{user_uid}`
- `POST /subjects`, `GET /subjects`, `GET/PATCH/DELETE /subjects/{subject_uid}`
- `POST /topics`, `GET /topics`, `GET/PATCH/DELETE /topics/{topic_uid}`
- `POST /tasks`, `GET /tasks`, `GET/PATCH/DELETE /tasks/{task_uid}`
- `GET /health`

Testy:

```powershell
python -m pytest -q --basetemp=.test-tmp
```
