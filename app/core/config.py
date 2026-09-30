import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "StudyFlow API")
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )
    ai_rate_limit_per_day: int = int(os.getenv("AI_RATE_LIMIT_PER_DAY", "300"))
    tts_rate_limit_per_day: int = int(os.getenv("TTS_RATE_LIMIT_PER_DAY", "500"))
    login_rate_limit_per_15_min: int = int(os.getenv("LOGIN_RATE_LIMIT_PER_15_MIN", "240"))
    failed_login_limit: int = int(os.getenv("FAILED_LOGIN_LIMIT", "20"))
    login_lock_minutes: int = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))
    registration_rate_limit_per_day: int = int(os.getenv("REGISTRATION_RATE_LIMIT_PER_DAY", "40"))
    metrics_token: str | None = os.getenv("METRICS_TOKEN")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
    gemini_fallback_model: str = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-flash-latest")
    gemini_tts_model: str = os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
    gemini_tts_voice: str = os.getenv("GEMINI_TTS_VOICE", "Despina")
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
            user=os.getenv("DB_USER", "postgres"), password=os.getenv("DB_PASSWORD", "postgres"),
            host=os.getenv("DB_HOST", "localhost"), port=os.getenv("DB_PORT", "5432"),
            name=os.getenv("DB_NAME", "studyflow"),
        ),
    )

    def __post_init__(self):
        if len(self.jwt_secret_key) < 32 or self.jwt_secret_key in {
            "development-only-secret-change-this-123456789",
            "replace-with-a-long-random-secret",
        }:
            raise ValueError("JWT_SECRET_KEY must be a unique secret of at least 32 characters")

settings = Settings()
