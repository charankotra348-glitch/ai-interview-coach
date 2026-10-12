from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ai-interview-coach"
    version: str = "0.1.0"
    environment: str = "local"
    log_level: str = "INFO"


settings = Settings()