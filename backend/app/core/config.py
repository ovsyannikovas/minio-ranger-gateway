import os

from pydantic import computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Конфигурация приложения MinIO-Ranger Gateway (через Pydantic Settings).
    Берёт .env на уровень выше backend/.
    Все основные переменные среды: MinIO, Ranger, Redis, Solr, почта, DB, безопасность.
    """
    API_V1_STR: str = "/api/v1"

    # --- Ranger
    RANGER_HOST: str = os.getenv("RANGER_HOST", "http://ranger:6080")
    RANGER_USER: str = os.getenv("RANGER_USER", "admin")
    RANGER_PASSWORD: str = os.getenv("RANGER_PASSWORD", "admin")
    RANGER_SERVICE_NAME: str = os.getenv("RANGER_SERVICE_NAME", "minio-service")
    RANGER_SERVICEDEF_NAME: str = os.getenv("RANGER_SERVICEDEF_NAME", "minio-service-def")
    RANGER_CACHE_TTL: int = os.getenv("RANGER_CACHE_TTL", 300)
    IP_WHITELIST_RAW: str | None = None

    # --- Solr
    SOLR_AUDIT_URL: str = os.getenv("SOLR_AUDIT_URL", "http://ranger-solr:8983/solr/ranger_audits")

    API_HOST: str = os.getenv("API_HOST", "localhost")

    @computed_field
    @property
    def IP_WHITELIST(self) -> list[str]:
        """Вычисляемое поле: парсит строку с IP-адресами в список"""
        if not self.IP_WHITELIST_RAW:
            return []
        return [ip.strip() for ip in self.IP_WHITELIST_RAW.split(",") if ip.strip()]


settings = Settings()  # type: ignore
