from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración obtenida desde variables de entorno o el archivo .env."""

    app_name: str = "Tienda de Ropa API"
    app_env: str = "development"
    app_debug: bool = False
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/ropa"
    jwt_secret: str = "change-this-value"
    cors_origins: list[str] = ["http://localhost:4200"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
