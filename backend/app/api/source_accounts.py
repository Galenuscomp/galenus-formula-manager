"""The pharmacy's logins to formula sources (admin, Users screen).

Stored encrypted; the password is never returned. "Test" logs in once with a
headless browser, so it takes a few seconds.
"""

from fastapi import APIRouter, HTTPException

from app import audit, crypto
from app.api.deps import DB, Admin
from app.api.schemas import SourceAccountIn
from app.models import SourceAccount
from app.search.automation import ACCOUNT_SOURCES, AUTOMATED_SOURCES, SearchCooldown, SearchFailed, check_login
from app.services import RuleViolation

router = APIRouter(prefix="/api/source-accounts", tags=["source-accounts"])


def _source(source: str) -> str:
    if source not in ACCOUNT_SOURCES:
        raise HTTPException(404, "Unknown source")
    return source


def _view(db) -> list[dict]:
    out = []
    for source in ACCOUNT_SOURCES:
        row = db.get(SourceAccount, source)
        try:
            username = crypto.decrypt(row.username_encrypted) if row else None
        except crypto.SecretError:
            username = None
        out.append({"source": source, "configured": row is not None, "username": username,
                    "downloads_supported": source in AUTOMATED_SOURCES,
                    "updated_at": row.updated_at.isoformat() if row else None})
    return out


@router.get("")
def list_accounts(_: Admin, db: DB):
    return _view(db)


@router.put("/{source}")
def save_account(source: str, body: SourceAccountIn, actor: Admin, db: DB):
    row = db.get(SourceAccount, _source(source))
    if row is None and not body.password:
        raise RuleViolation("Enter the password.")
    try:
        username = crypto.encrypt(body.username.strip())
        password = crypto.encrypt(body.password) if body.password else row.password_encrypted
    except crypto.SecretError as exc:
        raise RuleViolation(str(exc)) from exc
    row = row or SourceAccount(source=source)
    row.username_encrypted, row.password_encrypted, row.updated_by = username, password, actor.id
    db.add(row)
    audit.record(db, actor.id, "source_account_saved", "source_account", source)
    db.commit()
    return _view(db)


@router.delete("/{source}")
def delete_account(source: str, actor: Admin, db: DB):
    row = db.get(SourceAccount, _source(source))
    if row is not None:
        db.delete(row)
        audit.record(db, actor.id, "source_account_deleted", "source_account", source)
        db.commit()
    return _view(db)


@router.post("/{source}/test")
def test_account(source: str, _: Admin, db: DB):
    try:
        check_login(db, _source(source))
    except SearchCooldown as exc:
        raise RuleViolation(f"{source} says the account is in use elsewhere. Try again in 5 minutes. ({exc})") from exc
    except SearchFailed as exc:
        raise RuleViolation(str(exc)) from exc
    return {"ok": True}
