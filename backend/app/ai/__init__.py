from app.ai.base import ExtractionError, Extractor
from app.config import Settings


def get_extractor(settings: Settings) -> Extractor:
    if settings.ai_provider == "anthropic":
        from app.ai.anthropic_provider import AnthropicExtractor

        return AnthropicExtractor(
            settings.anthropic_model, fallbacks=settings.anthropic_fallbacks, timeout=settings.ai_timeout_seconds
        )
    if settings.ai_provider == "openai":
        if not settings.openai_model:
            raise ExtractionError("OPENAI_MODEL must be set when AI_PROVIDER=openai")
        from app.ai.openai_provider import OpenAIExtractor

        return OpenAIExtractor(settings.openai_model, timeout=settings.ai_timeout_seconds)
    if settings.ai_provider == "fake":
        from app.ai.fake import FakeExtractor

        return FakeExtractor()
    raise ExtractionError("AI extraction is not configured (set AI_PROVIDER)")
