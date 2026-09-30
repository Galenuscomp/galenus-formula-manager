from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Cookie, HTTPException, Request, Response
from sqlalchemy import select

from app import audit, mail, passwords
from app.api import serialize
from app.api.deps import COOKIE, DB, CurrentUser, check_origin
from app.api.schemas import ForgotPasswordIn, LoginIn, PasswordChangeIn, PasswordLinkCheckIn, PasswordLinkSetIn
from app.config import get_settings
from app.db import utcnow
from app.models import AuthSession, PasswordToken, User
from app.security import new_session_token, token_digest, verify_password

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
def change_password(body: PasswordChangeIn, user: CurrentUser, db: DB, background: BackgroundTasks):
    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(400, "Current password is incorrect")
    # Signs out every session, this one included.
    passwords.set_password(db, user, body.new_password)
    audit.record(db, user.id, "password_changed", "user", user.id)
    db.commit()
    background.add_task(mail.deliver, [mail.password_changed(user.email, user.full_name)])
    return {"ok": True, "signed_out": True}


FORGOT_INTERVAL = timedelta(minutes=5)


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordIn, request: Request, db: DB, background: BackgroundTasks):
    """E-mail a reset link (or a fresh invitation) to an active account. The answer is the same
    whether or not the address has an account, so it cannot be used to find accounts; at most
    one link per 5 minutes per account."""
    check_origin(request)
    if not mail.enabled():
        return {"ok": True, "email_enabled": False}
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is not None and user.is_active:
        recent = db.scalar(select(PasswordToken.id).where(
            PasswordToken.user_id == user.id, PasswordToken.used_at.is_(None),
            PasswordToken.created_at > utcnow() - FORGOT_INTERVAL))
        if recent is None:
            link = passwords.issue_link(db, user, None)
            audit.record(db, None, "password_link_requested_by_email", "user", user.id)
            db.commit()
            make = mail.invitation if link["purpose"] == "invite" else mail.password_reset
            background.add_task(mail.deliver, [make(user.email, user.full_name, mail.link(link["path"]))])
    return {"ok": True, "email_enabled": True}


# Invitation and reset links (see app.passwords). No session needed: the token is the credential.


@router.post("/password-link/check")
def check_password_link(body: PasswordLinkCheckIn, request: Request, db: DB):
    check_origin(request)
    link = passwords.find_link(db, body.token)
    return {"email": link.user.email, "full_name": link.user.full_name, "purpose": link.purpose}


@router.post("/password-link")
def use_password_link(body: PasswordLinkSetIn, request: Request, db: DB, background: BackgroundTasks):
    check_origin(request)
    link = passwords.find_link(db, body.token)
    passwords.set_password(db, link.user, body.new_password)
    link.used_at = utcnow()
    audit.record(db, link.user.id, f"password_set_by_{link.purpose}_link", "user", link.user.id)
    db.commit()
    if link.purpose == "reset":  # a first password (invitation) is not a change worth an alert
        background.add_task(mail.deliver, [mail.password_changed(link.user.email, link.user.full_name)])
    return {"ok": True, "email": link.user.email}
