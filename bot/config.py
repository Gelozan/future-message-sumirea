from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from datetime import date


class Settings(BaseSettings):
    # Telegram
    bot_token: str

    # PostgreSQL
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_port: int
    database_url: str

    # Настройки сбора сообщений
    collection_start: date
    collection_end: date

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
