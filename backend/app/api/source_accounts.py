"""Each user's own logins to formula sources (Account screen).

Downloads run with the login of the user who asked for them. Stored encrypted;
the password is never returned. "Test login" signs in once with a headless
browser (a few seconds) and its result is kept and shown next to the account.
"""

from fastapi import APIRouter, HTTPException

from app import audit, crypto
from app.api.deps import DB, CurrentUser
from app.api.schemas import SourceAccountIn
from app.db import utcnow
from app.models import SourceAccount
from app.search.automation import ACCOUNT_SOURCES, AUTOMATED_SOURCES, SearchCooldown, SearchFailed, check_login
from app.services import RuleViolation

router = APIRouter(prefix="/api/source-accounts", tags=["source-accounts"])


def _source(source: str) -> str:
    if source not in ACCOUNT_SOURCES:
        raise HTTPException(404, "Unknown source")
    return source


def _view(db, user) -> list[dict]:
    out = []
    for source in ACCOUNT_SOURCES:
        row = db.get(SourceAccount, (user.id, source))
        try:
            username = crypto.decrypt(row.username_encrypted) if row else None
        except crypto.SecretError:
            username = None
        out.append({
            "source": source, "configured": row is not None, "username": username,
            "downloads_supported": source in AUTOMATED_SOURCES,
            "updated_at": row.updated_at.isoformat() if row else None,
            "checked_at": row.checked_at.isoformat() if row and row.checked_at else None,
            "check_ok": row.check_ok if row else None,
            "check_message": row.check_message if row else None,
        })
    return out


@router.get("")
def list_accounts(user: CurrentUser, db: DB):
    return _view(db, user)


@router.put("/{source}")
def save_account(source: str, body: SourceAccountIn, user: CurrentUser, db: DB):
    row = db.get(SourceAccount, (user.id, _source(source)))
    if row is None and not body.password:
        raise RuleViolation("Enter the password.")
    try:
        username = crypto.encrypt(body.username.strip())
        password = crypto.encrypt(body.password) if body.password else row.password_encrypted
    except crypto.SecretError as exc:
        raise RuleViolation(str(exc)) from exc
    row = row or SourceAccount(user_id=user.id, source=source)
    row.username_encrypted, row.password_encrypted, row.updated_by = username, password, user.id
    row.checked_at = row.check_ok = row.check_message = None  # a changed login is untested
    db.add(row)
    audit.record(db, user.id, "source_account_saved", "source_account", source)
    db.commit()
    return _view(db, user)


@router.delete("/{source}")
def delete_account(source: str, user: CurrentUser, db: DB):
    row = db.get(SourceAccount, (user.id, _source(source)))
    if row is not None:
        db.delete(row)
        audit.record(db, user.id, "source_account_deleted", "source_account", source)
        db.commit()
    return _view(db, user)


@router.post("/{source}/test")
def test_account(source: str, user: CurrentUser, db: DB):
    row = db.get(SourceAccount, (user.id, _source(source)))
    if row is None:
        raise RuleViolation("Save the login first.")
    ok, message = True, f"Signed in to {source} successfully."
    try:
        check_login(db, source, user.id)
    except SearchCooldown:
        ok, message = False, f"{source} says the account is in use elsewhere. Try again in 5 minutes."
    except SearchFailed as exc:
        ok, message = False, str(exc)
    row.checked_at, row.check_ok, row.check_message = utcnow(), ok, message[:500]
    db.commit()
    return {"ok": ok, "message": message, "accounts": _view(db, user)}
