from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables or a local `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    nebius_api_key: SecretStr
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    # Optional: when unset, Tavily search runs in its rate-limited keyless mode.
    tavily_api_key: SecretStr | None = None

    # Model routing: a small model for intake, a vision-language model for the photo,
    # and the largest reasoning model for the final plan.
    model_fast: str = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
    model_vision: str = "nvidia/Nemotron-3.5-Super-VL"
    model_reasoning: str = "nvidia/Nemotron-3-Ultra-550b-a55b"

    request_timeout_s: float = 120.0
    max_image_bytes: int = 8 * 1024 * 1024
    search_results_per_query: int = 4

    web_dir: Path = PROJECT_ROOT / "web"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
