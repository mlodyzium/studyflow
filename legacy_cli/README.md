# Legacy CLI

To jest poprzednia, konsolowa wersja StudyFlow oparta na pliku `data.json`.
Zostala zachowana jako archiwum; aktualnie rozwijana aplikacja znajduje sie w
`app/` i korzysta z FastAPI oraz PostgreSQL.

Uruchomienie archiwalnej wersji utworzy lokalny `data.json` (ignorowany przez Git):

```powershell
python -m legacy_cli.main
```
