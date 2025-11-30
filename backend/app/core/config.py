import secrets
import warnings
from typing import Annotated, Any, Literal

import os
from typing_extensions import Self

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str] | str:
    """Парсер настроек CORS из строки/массива."""
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    """
    Конфигурация приложения MinIO-Ranger Gateway (через Pydantic Settings).
    Берёт .env на уровень выше backend/.
    Все основные переменные среды: MinIO, Ranger, Redis, Solr, почта, DB, безопасность.
    """
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"  #: url-prefix
    SECRET_KEY: str = secrets.token_urlsafe(32)  #: секрет для JWT/шифрования
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  #: токен срок
    FRONTEND_HOST: str | None = None
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []  #: CORS-список

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        """Все CORS-источники, учитывая FRONTEND_HOST/настройки."""
        origins = [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS]
        if self.FRONTEND_HOST:
            origins.append(self.FRONTEND_HOST)
        return origins

    PROJECT_NAME: str = "MinIO-Ranger Gateway"
    SENTRY_DSN: HttpUrl | None = None  #: monitoring
    POSTGRES_SERVER: str | None = None
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn | None:
        """URI для SQLAlchemy/Alembic по текущим env."""
        if not all([self.POSTGRES_SERVER, self.POSTGRES_USER, self.POSTGRES_DB]):
            return None
        return PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: EmailStr | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        """Если EMAILS_FROM_NAME не задан — берет PROJECT_NAME."""
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field
    @property
    def emails_enabled(self) -> bool:
        """Включена ли отправка email — по SMTP_HOST + email настроен."""
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr | None = None
    FIRST_SUPERUSER_PASSWORD: str | None = None

    # --- Ranger
    RANGER_HOST: str = os.getenv("RANGER_HOST", "http://ranger:6080")
    RANGER_USER: str = os.getenv("RANGER_USER", "admin")
    RANGER_PASSWORD: str = os.getenv("RANGER_PASSWORD", "admin")
    RANGER_SERVICE_NAME: str = os.getenv("RANGER_SERVICE_NAME", "minio-dev")
    RANGER_CACHE_TTL: int = os.getenv("RANGER_CACHE_TTL", 300)

    # --- MinIO
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    MINIO_ROOT_USER: str = "admin"
    MINIO_ROOT_PASSWORD: str = "password"

    # --- Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "redispass123")

    # --- Solr
    SOLR_AUDIT_URL: str = os.getenv("SOLR_AUDIT_URL", "http://solr:8983/solr/ranger_audits")

    API_HOST: str = os.getenv("API_HOST", "localhost")

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        """Проверка наличия дефолтных значений секретов (SECURITY предупреждение)."""
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        """Валидация: при деплое не должно быть changethis для важных секретов."""
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        if self.POSTGRES_SERVER:
            self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        if self.FIRST_SUPERUSER:
            self._check_default_secret(
                "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
            )
        return self


settings = Settings()  # type: ignore
