from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/insurance_compare"

    # Security
    SECRET_KEY: str = "change-me"

    # File uploads
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 5

    # CORS – comma-separated list in .env is automatically split by pydantic-settings
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Groq
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # LLM provider selection
    LLM_PROVIDER: str = "groq"  # "groq" | "ollama"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:14b"
    OLLAMA_TIMEOUT_SECONDS: int = 180

    # Google Sheets integration
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""
    GOOGLE_SHEETS_SHARE_EMAIL: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def upload_path(self) -> str:
        path = os.path.abspath(self.UPLOAD_DIR)
        os.makedirs(path, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
