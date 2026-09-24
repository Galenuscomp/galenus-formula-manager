from dataclasses import dataclass, field
from typing import Any, Protocol


class ExtractionError(Exception):
    """Extraction failed. `retryable` tells the job runner whether to try again."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class ExtractionResult:
    output: dict[str, Any]
    model: str
    usage: dict[str, Any] = field(default_factory=dict)


class Extractor(Protocol):
    provider: str
    model: str

    def extract(self, pdf: bytes, filename: str) -> ExtractionResult: ...
