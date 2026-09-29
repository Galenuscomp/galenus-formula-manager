"""Downloading formula PDFs from the sources' websites with the pharmacy's own login.

Each source with automation has an adapter (a headless browser, see
compounding_today.py). Runs only inside background jobs, never in an HTTP
request, so a slow site cannot freeze the UI. The only exception is the admin's
"Test login" button, which runs one login.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crypto
from app.models import SourceAccount

# Sources with a download adapter. Every other source is manual upload.
AUTOMATED_SOURCES = {"CompoundingToday"}
# Sources whose login the admin can store (MEDISCA's download comes later).
ACCOUNT_SOURCES = ("CompoundingToday", "MEDISCA")


class SearchCooldown(Exception):
    """The source refused for now (e.g. CompoundingToday "Account in Use"); retry later."""


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


@dataclass
class Credentials:
    username: str
    password: str


def configured_sources(db: Session) -> set[str]:
    """Sources the worker can download from: an adapter exists and a login is saved."""
    saved = set(db.scalars(select(SourceAccount.source)))
    return AUTOMATED_SOURCES & saved


def credentials(db: Session, source: str) -> Credentials:
    row = db.get(SourceAccount, source)
    if row is None:
        raise SearchFailed(f"No {source} login is saved. An admin adds it under Users > Source accounts.",
                           retryable=False)
    try:
        return Credentials(crypto.decrypt(row.username_encrypted), crypto.decrypt(row.password_encrypted))
    except crypto.SecretError as exc:
        raise SearchFailed(f"The saved {source} login cannot be read; save it again.", retryable=False) from exc


def fetch(db: Session, source: str, *, active_ingredient: str, strength: str = "", dosage_form: str = "",
          formula_id: str = "", title: str = "") -> FoundDocument:
    """Download one formula PDF: the given formula_id, else the first keyword-search hit."""
    if source not in AUTOMATED_SOURCES:
        raise SearchFailed(f"{source} has no automated download; upload the PDF instead.", retryable=False)
    creds = credentials(db, source)
    from app.search import compounding_today

    return compounding_today.fetch(creds, active_ingredient=active_ingredient, formula_id=formula_id, title=title)


def check_login(db: Session, source: str) -> None:
    if source not in AUTOMATED_SOURCES:
        raise SearchFailed(f"Automated download from {source} is not available yet.", retryable=False)
    creds = credentials(db, source)
    from app.search import compounding_today

    compounding_today.check_login(creds)
