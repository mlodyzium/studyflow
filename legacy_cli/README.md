# Legacy CLI

To jest poprzednia, konsolowa wersja StudyFlow rozwinięta o logowanie, pełny
CRUD, sesje nauki i wyniki egzaminów. Korzysta z tej samej bazy PostgreSQL oraz
modeli co aktualne API, ale pozostaje oddzielnym interfejsem archiwalnym.

Przed uruchomieniem skonfiguruj `.env` i zastosuj migracje Alembic zgodnie z
głównym README. Następnie wykonaj:

```powershell
python -m legacy_cli.main
```
