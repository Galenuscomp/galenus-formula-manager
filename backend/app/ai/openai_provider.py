import base64
import json

import openai

from app.ai.base import ExtractionError, ExtractionResult
from app.ai.schema import EXTRACTION_INSTRUCTIONS, strict_schema


class OpenAIExtractor:
    provider = "openai"

    def __init__(self, model: str, *, api_key: str | None = None, timeout: float = 240.0):
        self.model = model
        self.client = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=2)

    def verify(self) -> None:
        try:
            self.client.models.retrieve(self.model)
        except openai.AuthenticationError as exc:
            raise ExtractionError("OpenAI rejected the API key") from exc
        except openai.NotFoundError as exc:
            raise ExtractionError(f'OpenAI has no model named "{self.model}"') from exc
        except openai.APIStatusError as exc:
            raise ExtractionError(f"OpenAI returned error {exc.status_code}") from exc
        except openai.APIConnectionError as exc:
            raise ExtractionError("Could not reach OpenAI", retryable=True) from exc

    def extract(self, pdf: bytes, filename: str) -> ExtractionResult:
        data_url = "data:application/pdf;base64," + base64.standard_b64encode(pdf).decode("ascii")
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=EXTRACTION_INSTRUCTIONS,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_file", "filename": filename, "file_data": data_url},
                            {"type": "input_text", "text": "Extract the master formula from this document."},
                        ],
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "master_formula",
                        "schema": strict_schema(),
                        "strict": True,
                    }
                },
            )
        except openai.RateLimitError as exc:
            raise ExtractionError("AI provider rate limit reached", retryable=True) from exc
        except openai.APIStatusError as exc:
            raise ExtractionError(
                f"AI provider error {exc.status_code}", retryable=exc.status_code >= 500
            ) from exc
        except openai.APIConnectionError as exc:
            raise ExtractionError("Could not reach AI provider", retryable=True) from exc

        if response.status == "incomplete":
            raise ExtractionError("Extraction output was incomplete")
        text = response.output_text
        if not text:
            raise ExtractionError("AI response contained no structured output")
        try:
            output = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ExtractionError("AI response was not valid JSON") from exc
        usage = {}
        if response.usage:
            usage = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
        return ExtractionResult(output=output, model=response.model or self.model, usage=usage)
