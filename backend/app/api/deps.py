from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, utcnow
from app.models import AuthSession, User
from app.security import can_approve, can_prepare, token_digest

COOKIE = "fm_session"
DB = Annotated[Session, Depends(get_db)]


def check_origin(request: Request) -> None:
    """Reject cross-site state changes. Cookies are SameSite=Lax as well."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    expected = get_settings().public_origin
    origin = request.headers.get("origin")
    if expected and origin and origin.rstrip("/") != expected.rstrip("/"):
        raise HTTPException(403, "Cross-origin request rejected")
    if request.headers.get("x-requested-with") != "fm":
        raise HTTPException(403, "Missing request header")


def current_user(request: Request, db: DB, fm_session: Annotated[str | None, Cookie()] = None) -> User:
    check_origin(request)
    if not fm_session:
        raise HTTPException(401, "Not signed in")
    session = db.scalar(select(AuthSession).where(AuthSession.token_digest == token_digest(fm_session)))
    if session is None or session.revoked_at is not None or session.expires_at <= utcnow():
        raise HTTPException(401, "Session expired")
    if not session.user.is_active:
        raise HTTPException(401, "Account disabled")
    return session.user


CurrentUser = Annotated[User, Depends(current_user)]


def preparer(user: CurrentUser) -> User:
    if not can_prepare(user.role):
        raise HTTPException(403, "Your role cannot prepare formulas")
    return user


def pharmacist(user: CurrentUser) -> User:
    if not can_approve(user.role):
        raise HTTPException(403, "Only pharmacists can decide on drafts")
    return user


def admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Admins only")
    return user


Preparer = Annotated[User, Depends(preparer)]
Pharmacist = Annotated[User, Depends(pharmacist)]
Admin = Annotated[User, Depends(admin)]
