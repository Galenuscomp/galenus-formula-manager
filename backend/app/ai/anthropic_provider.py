import base64
import json

import anthropic

from app.ai.base import ExtractionError, ExtractionResult
from app.ai.schema import EXTRACTION_INSTRUCTIONS, strict_schema

_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicExtractor:
    provider = "anthropic"

    def __init__(self, model: str, *, fallbacks: str = "default", timeout: float = 240.0):
        self.model = model
        self.fallbacks = fallbacks
        self.client = anthropic.Anthropic(timeout=timeout, max_retries=2)

    def extract(self, pdf: bytes, filename: str) -> ExtractionResult:
        params = dict(
            model=self.model,
            max_tokens=16000,
            system=EXTRACTION_INSTRUCTIONS,
            output_config={"format": {"type": "json_schema", "schema": strict_schema()}},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": base64.standard_b64encode(pdf).decode("ascii"),
                            },
                            "title": filename,
                        },
                        {"type": "text", "text": "Extract the master formula from this document."},
                    ],
                }
            ],
        )
        try:
            if self.fallbacks == "default":
                response = self.client.beta.messages.create(
                    betas=[_FALLBACK_BETA], fallbacks="default", **params
                )
            else:
                response = self.client.messages.create(**params)
        except anthropic.RateLimitError as exc:
            raise ExtractionError("AI provider rate limit reached", retryable=True) from exc
        except anthropic.APIStatusError as exc:
            raise ExtractionError(
                f"AI provider error {exc.status_code}", retryable=exc.status_code >= 500
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise ExtractionError("Could not reach AI provider", retryable=True) from exc

        if response.stop_reason == "refusal":
            raise ExtractionError("The AI model declined to process this document")
        if response.stop_reason == "max_tokens":
            raise ExtractionError("Document too long: extraction output was truncated")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise ExtractionError("AI response contained no structured output")
        try:
            output = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ExtractionError("AI response was not valid JSON") from exc
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return ExtractionResult(output=output, model=response.model, usage=usage)
