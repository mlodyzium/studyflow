from sqlalchemy import inspect

from data import models  # rejestruje modele w Base.metadata
from data.database import Base, engine


def tables_exist() -> bool:
    """Sprawdza, czy w bazie istnieją już nasze tabele."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    expected_tables = Base.metadata.tables.keys()
    return all(table in existing_tables for table in expected_tables)


def init_db():
    if tables_exist():
        print("Baza danych już skonfigurowana.")
    else:
        Base.metadata.create_all(engine)
        print("Utworzono brakujące tabele w bazie danych.")


if __name__ == "__main__":
    init_db()