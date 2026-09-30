# Legacy CLI

This is the archived command-line interface for StudyFlow. It provides account access, CRUD operations, study sessions, and exam results using the same PostgreSQL models as the API.

Configure `.env` and apply the Alembic migrations described in the root README before running:

```sh
python -m legacy_cli.main
```

The React application is the primary interface. The CLI is retained to document the project's evolution.
