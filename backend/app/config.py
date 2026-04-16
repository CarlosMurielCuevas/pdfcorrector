# Configuración centralizada usando pydantic-settings
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configuración de la aplicación cargada desde variables de entorno."""

    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    allowed_origins: str = "http://localhost:4200"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def origins_list(self) -> list[str]:
        """Devuelve la lista de orígenes permitidos para CORS."""
        return [o.strip() for o in self.allowed_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Devuelve una instancia cacheada de la configuración."""
    return Settings()