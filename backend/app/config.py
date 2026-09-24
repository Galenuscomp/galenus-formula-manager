from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/app.db"
    data_dir: Path = Path("./data")
    # Origin the browser uses (e.g. https://formulas.example.com). When set,
    # mutating requests from any other Origin are rejected.
    public_origin: str | None = None
    session_cookie_secure: bool = True
    session_ttl_hours: int = 12

    ai_provider: Literal["anthropic", "openai", "fake", "none"] = "none"
    anthropic_model: str = "claude-opus-5"
    # "default" enables server-side refusal fallbacks; "off" disables them.
    anthropic_fallbacks: Literal["default", "off"] = "default"
    openai_model: str | None = None
    ai_timeout_seconds: float = 240.0

    # External automation worker that downloads formula PDFs (CompoundingToday).
    formula_automation_url: str | None = None
    formula_automation_api_key: str | None = None
    automation_timeout_seconds: float = 150.0

    job_lease_seconds: int = 420
    job_max_attempts: int = 3
    worker_poll_seconds: float = 2.0
    embedded_worker: bool = False

    max_upload_mb: int = Field(default=25, ge=1, le=100)

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"


@lru_cache
def get_settings() -> Settings:
    return Settings()
