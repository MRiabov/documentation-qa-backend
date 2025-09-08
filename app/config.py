from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    # Base URL to the TGI server (docker-compose service + internal port)
    TGI_BASE_URL: AnyHttpUrl = "http://tgi:80"

    # Generation parameters
    MAX_NEW_TOKENS: int = 2048
    TEMPERATURE: float = 0.0
    TOP_P: float = 0.9
    STOP_SEQUENCES: List[str] = ["</json>"]

    # OpenRouter fallback
    OPENROUTER_BASE_URL: AnyHttpUrl = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "moonshotai/kimi-k2:free"
    OPENROUTER_FALLBACK_KEY: Optional[str] = None

    # Regeneration behavior
    RETRIES_ON_MALFORMED: int = 1  # number of extra attempts when model output is malformed

    # Code editing behavior
    CODE_EDIT_THRESHOLD_RATIO: float = 0.15  # if >= fraction of chars in fenced code, allow code edits

    # Linter configuration
    ENABLE_LINTER: bool = True
    LINTER_LANGUAGE: str = "en-US"

    # API
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS
    # Provide a JSON array in env, e.g. ["https://your-site.netlify.app"]
    CORS_ALLOW_ORIGINS: List[str] = []

    # Pydantic v2-style config
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
