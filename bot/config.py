from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str
    gemini_api_key: str
    # Рекомендуемые: gemini-3.8-flash (актуально для новых ключей)
    gemini_model: str = "gemini-3.8-flash"

    database_url: str = "sqlite+aiosqlite:///./data/bot.db"
    redis_url: str = ""
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
