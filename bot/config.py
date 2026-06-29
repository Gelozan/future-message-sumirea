from pydantic_settings import BaseSettings
from pydantic import field_validator
from datetime import date


class Settings(BaseSettings):
    # Telegram
    bot_token: str

    # PostgreSQL
    postgres_db: str
    postgres_user: str
    postgres_password: str
    database_url: str

    # Настройки сбора сообщений
    collection_start: date
    collection_end: date

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
