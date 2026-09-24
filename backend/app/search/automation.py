"""Client for the external formula automation worker (ported from the Base44
function startFormulaSourceSearch). Runs only inside background jobs, never in
an HTTP request, so a slow or sleeping worker cannot freeze the UI."""

import re
from dataclasses import dataclass
from urllib.parse import unquote

import httpx

from app.config import Settings

# Sources with an automated download flow. Every other source is manual upload.
AUTOMATED_SOURCES = {"CompoundingToday"}


class SearchCooldown(Exception):
    pass


class SearchNoResults(Exception):
    pass


class SearchFailed(Exception):
    def __init__(self, message: str, *, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class FoundDocument:
    pdf: bytes
    filename: str
    source_name: str
    source_formula_id: str
    title: str
    url: str


_FILENAME = re.compile(r"filename\*?=(?:UTF-8'')?[\"']?([^\"';\n]+)[\"']?", re.I)


def automation_configured(settings: Settings) -> bool:
    return bool(settings.formula_automation_url and settings.formula_automation_api_key)


def fetch_compounding_today(
    settings: Settings, *, active_ingredient: str, strength: str, dosage_form: str
) -> FoundDocument:
    if not automation_configured(settings):
        raise SearchFailed("Automated search is not configured on this server", retryable=False)
    try:
        response = httpx.post(
            settings.formula_automation_url,  # type: ignore[arg-type]
            json={"active_ingredient": active_ingredient, "strength": strength, "dosage_form": dosage_form},
            headers={"x-api-key": settings.formula_automation_api_key or ""},
            timeout=settings.automation_timeout_seconds,
        )
    except httpx.TimeoutException as exc:
        raise SearchFailed("Search worker timed out", retryable=True) from exc
    except httpx.HTTPError as exc:
        raise SearchFailed("Could not reach search worker", retryable=True) from exc

    if response.status_code == 429:
        raise SearchCooldown()
    if response.status_code == 404:
        raise SearchNoResults()
    if response.status_code >= 400:
        raise SearchFailed(
            f"Search worker returned {response.status_code}", retryable=response.status_code >= 500
        )
    if not response.content.startswith(b"%PDF-"):
        raise SearchFailed("Search worker did not return a PDF", retryable=False)

    filename = "compounding-formula.pdf"
    match = _FILENAME.search(response.headers.get("content-disposition", ""))
    if match:
        filename = unquote(match.group(1).strip()) or filename
    h = response.headers
    return FoundDocument(
        pdf=response.content,
        filename=filename[:300],
        source_name=h.get("x-source") or "CompoundingToday",
        source_formula_id=h.get("x-source-formula-id", "")[:200],
        title=h.get("x-source-formula-title", "")[:500],
        url=h.get("x-source-formula-url", "")[:2000],
    )
