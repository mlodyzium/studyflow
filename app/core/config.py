import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "StudyFlow API")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://{user}:{password}@{host}:{port}/{name}".format(
            user=os.getenv("DB_USER", "postgres"), password=os.getenv("DB_PASSWORD", "postgre"),
            host=os.getenv("DB_HOST", "localhost"), port=os.getenv("DB_PORT", "5432"),
            name=os.getenv("DB_NAME", "studyflow"),
        ),
    )

settings = Settings()
