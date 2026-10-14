import secrets
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_ENVIRONMENTS = {"local", "ci", "test"}
MIN_JWT_SECRET_CHARS = 32


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
    llm_budget_s: float = Field(default=45.0, ge=10)

    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    jwt_secret: SecretStr | None = None
    jwt_ttl_minutes: int = Field(default=30, ge=1, le=1440)

    @model_validator(mode="after")
    def _check_jwt_secret(self):
        value = self.jwt_secret.get_secret_value() if self.jwt_secret else ""
        if not value:
            if self.environment not in DEV_ENVIRONMENTS:
                raise ValueError("JWT_SECRET must be set outside development")
            # Development only: a random secret for this process. Tokens stop working
            # when the server restarts; set JWT_SECRET in .env to keep them.
            self.jwt_secret = SecretStr(secrets.token_urlsafe(48))
        elif len(value) < MIN_JWT_SECRET_CHARS:
            raise ValueError(f"JWT_SECRET must be at least {MIN_JWT_SECRET_CHARS} characters")
        return self


settings = Settings()