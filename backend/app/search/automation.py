"""Downloading formula PDFs from the sources' websites with the user's own login.

Each source with automation has an adapter (a headless browser, see
compounding_today.py and medisca.py). Every user saves their own logins; a
download runs with the login of the user who asked for it. Runs only inside
background jobs, never in an HTTP request, so a slow site cannot freeze the UI.
The only exception is "Test login", which signs in once.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crypto
from app.models import SourceAccount

# Sources with a download adapter. Every other source is manual upload.
AUTOMATED_SOURCES = {"CompoundingToday", "MEDISCA"}
# Sources whose login a user can store.
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
    # Names this account's saved browser session, lock and cooldown (one per user and source).
    key: str = "default"


def configured_sources(db: Session, user_id: str | None) -> set[str]:
    """Sources this user can download from: an adapter exists and they saved a login."""
    if not user_id:
        return set()
    saved = set(db.scalars(select(SourceAccount.source).where(SourceAccount.user_id == user_id)))
    return AUTOMATED_SOURCES & saved


def credentials(db: Session, source: str, user_id: str | None) -> Credentials:
    row = db.get(SourceAccount, (user_id, source)) if user_id else None
    if row is None:
        raise SearchFailed(f"No {source} login is saved for the user who asked for this download. "
                           "Add it under Account > Source accounts.", retryable=False)
    try:
        return Credentials(crypto.decrypt(row.username_encrypted), crypto.decrypt(row.password_encrypted),
                           key=f"{source.lower()}-{user_id[:8]}")
    except crypto.SecretError as exc:
        raise SearchFailed(f"The saved {source} login cannot be read; save it again.", retryable=False) from exc


def fetch(db: Session, source: str, *, user_id: str | None, active_ingredient: str, strength: str = "",
          dosage_form: str = "", formula_id: str = "", title: str = "") -> FoundDocument:
    """Download one formula PDF: the given formula_id, else the best keyword-search hit."""
    if source not in AUTOMATED_SOURCES:
        raise SearchFailed(f"{source} has no automated download; upload the PDF instead.", retryable=False)
    creds = credentials(db, source, user_id)
    return _adapter(source).fetch(creds, active_ingredient=active_ingredient, formula_id=formula_id, title=title,
                                  strength=strength, dosage_form=dosage_form)


def check_login(db: Session, source: str, user_id: str) -> None:
    if source not in AUTOMATED_SOURCES:
        raise SearchFailed(f"Automated download from {source} is not available.", retryable=False)
    _adapter(source).check_login(credentials(db, source, user_id))


def _adapter(source: str):
    if source == "MEDISCA":
        from app.search import medisca

        return medisca
    from app.search import compounding_today

    return compounding_today
