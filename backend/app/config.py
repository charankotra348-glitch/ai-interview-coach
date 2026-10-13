from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ai-interview-coach"
    version: str = "0.1.0"
    environment: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://coach:coach@localhost:5433/coach"

    llm_provider: Literal["gemini", "ollama"] = "gemini"
    llm_timeout_s: float = Field(default=60.0, ge=10)
    llm_max_attempts: int = 3

    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"


settings = Settings()