"""
api/config.py — Konfigurasi Terpusat KBMS Shavira
Menggunakan pydantic-settings untuk membaca dari .env
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "..", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Qdrant Vector DB
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    collection_name: str = "shavira_undiksha_kb"

    # Embedding Model
    embed_model: str = "intfloat/multilingual-e5-large"

    # LLM Backend
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str = ""

    # Admin Authentication
    admin_username: str = "admin"
    admin_password: str = "shavira-undiksha-2026"

    # Analytics
    analytics_db_path: str = "data/analytics.db"

    # Crawler
    crawler_default_domain: str = "undiksha.ac.id"
    crawler_max_pages: int = 50

    # App
    app_env: str = "development"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache()
def get_settings() -> Settings:
    """Singleton: Settings dibaca sekali dan di-cache."""
    return Settings()
