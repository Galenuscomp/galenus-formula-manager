from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from sqlalchemy import select

from app import audit
from app.api import serialize
from app.api.deps import COOKIE, DB, CurrentUser, check_origin
from app.api.schemas import LoginIn, PasswordChangeIn
from app.config import get_settings
from app.db import utcnow
from app.models import AuthSession, User
from app.security import hash_password, new_session_token, token_digest, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: DB):
    check_origin(request)
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if not verify_password(user.password_hash if user else None, body.password) or not user or not user.is_active:
        raise HTTPException(401, "Incorrect e-mail or password")
    settings = get_settings()
    token = new_session_token()
    db.add(
        AuthSession(
            user_id=user.id,
            token_digest=token_digest(token),
            expires_at=utcnow() + timedelta(hours=settings.session_ttl_hours),
        )
    )
    audit.record(db, user.id, "login", "user", user.id)
    db.commit()
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    return serialize.user(user)


@router.post("/logout")
def logout(request: Request, response: Response, db: DB, fm_session: Annotated[str | None, Cookie()] = None):
    check_origin(request)
    if fm_session:
        session = db.scalar(select(AuthSession).where(AuthSession.token_digest == token_digest(fm_session)))
        if session and session.revoked_at is None:
            session.revoked_at = utcnow()
            db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: CurrentUser):
    return serialize.user(user)


@router.post("/password")
def change_password(body: PasswordChangeIn, user: CurrentUser, db: DB):
    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    # Sign out every other session.
    for s in db.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))):
        s.revoked_at = utcnow()
    audit.record(db, user.id, "password_changed", "user", user.id)
    db.commit()
    return {"ok": True, "signed_out": True}
