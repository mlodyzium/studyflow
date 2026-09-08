import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "StudyFlow API")
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    jwt_secret_key: str = os.getenv(
        "JWT_SECRET_KEY", "development-only-secret-change-this-123456789"
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
    gemini_fallback_model: str = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-flash-latest")
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
            ).split(",")
            if origin.strip()
        )
    )
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://{user}:{password}@{host}:{port}/{name}".format(
            user=os.getenv("DB_USER", "postgres"), password=os.getenv("DB_PASSWORD", "postgre"),
            host=os.getenv("DB_HOST", "localhost"), port=os.getenv("DB_PORT", "5432"),
            name=os.getenv("DB_NAME", "studyflow"),
        ),
    )

settings = Settings()
