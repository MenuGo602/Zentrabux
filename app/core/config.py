from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── App ────────────────────────────────────────────
    APP_NAME: str = "Zentra"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str
    API_V1_PREFIX: str = "/api/v1"
    # Production CORS uchun ruxsat etilgan domenlar (main.py'da ishlatiladi)
    ALLOWED_HOSTS: list[str] = ["*"]
    # React dashboard manzili (Telegram Login Widget shu domenga sozlanadi)
    FRONTEND_URL: str = "http://localhost:5173"

    # ─── Database ───────────────────────────────────────
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ─── Redis ──────────────────────────────────────────
    REDIS_URL: str
    REDIS_CACHE_TTL: int = 3600

    # ─── Auth ───────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ─── Telegram ───────────────────────────────────────
    BOT_TOKEN: str = ""
    WEBHOOK_URL: str = ""
    WEBHOOK_SECRET: str = ""
    # Bot konteynerining FastAPI'ga murojaat qilishi uchun bazaviy manzil
    # (docker-compose ichida http://api:8000, lokal ishga tushirishda http://localhost:8000)
    API_BASE_URL: str = "http://localhost:8000"

    # ─── AI ─────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str = ""
    AI_MAX_TOKENS: int = 1000
    AI_TEMPERATURE: float = 0.1

    # ─── Storage ────────────────────────────────────────
    STORAGE_BACKEND: Literal["local", "s3", "minio"] = "local"
    STORAGE_LOCAL_PATH: str = "./uploads"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_BUCKET_NAME: str = "zentra-files"
    AWS_REGION: str = "us-east-1"
    MINIO_URL: str = ""   # MinIO uchun (masalan http://localhost:9000); AWS S3 uchun bo'sh qoldiriladi

    # ─── Document Generation ──────────────────────────────
    # Lotin o'zbekcha tutuq belgisi (o', g') PDF'da to'g'ri chiqishi uchun
    # Unicode TTF shrift kerak (masalan DejaVuSans.ttf). Bo'sh bo'lsa,
    # standart Helvetica ishlatiladi (tutuq belgisi noto'g'ri ko'rinishi mumkin).
    PDF_FONT_PATH: str = ""
    PDF_FONT_BOLD_PATH: str = ""

    # ─── Email ──────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "Zentra <noreply@zentra.uz>"

    # ─── SMS ────────────────────────────────────────────
    ESKIZ_EMAIL: str = ""
    ESKIZ_PASSWORD: str = ""
    ESKIZ_FROM: str = "4546"

    # ─── Sentry ─────────────────────────────────────────
    SENTRY_DSN: str = ""

    # ─── Celery ─────────────────────────────────────────
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("Faqat PostgreSQL qo'llab-quvvatlanadi")
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
