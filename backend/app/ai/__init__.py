from dataclasses import dataclass

from app.ai.base import ExtractionError, Extractor
from app.config import Settings

USER_PROVIDERS = ("openai", "anthropic")


@dataclass(frozen=True)
class AIConfig:
    provider: str
    model: str
    # None: the SDK reads the server's key from the environment (.env).
    api_key: str | None = None


def server_config(settings: Settings) -> AIConfig | None:
    """The server default from .env, used by users who have not chosen their own."""
    if settings.ai_provider == "anthropic":
        return AIConfig("anthropic", settings.anthropic_model)
    if settings.ai_provider == "openai" and settings.openai_model:
        return AIConfig("openai", settings.openai_model)
    if settings.ai_provider == "fake":
        return AIConfig("fake", "fake-extractor")
    return None


def get_extractor(config: AIConfig, settings: Settings) -> Extractor:
    if config.provider == "anthropic":
        from app.ai.anthropic_provider import AnthropicExtractor

        return AnthropicExtractor(
            config.model, api_key=config.api_key, fallbacks=settings.anthropic_fallbacks,
            timeout=settings.ai_timeout_seconds,
        )
    if config.provider == "openai":
        from app.ai.openai_provider import OpenAIExtractor

        return OpenAIExtractor(config.model, api_key=config.api_key, timeout=settings.ai_timeout_seconds)
    if config.provider == "fake":
        from app.ai.fake import FakeExtractor

        return FakeExtractor()
    raise ExtractionError(f"Unknown AI provider: {config.provider}")
