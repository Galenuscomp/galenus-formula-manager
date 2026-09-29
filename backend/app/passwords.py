"""Setting passwords: the rules, and one-time links for invitations and resets.

There is no e-mail service. An admin creates the link and sends it to the user
(e-mail, WhatsApp, ...); the user opens it and chooses their own password, so
the admin never knows it. A new link replaces any earlier unused one.
"""

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import AuthSession, PasswordToken, User
from app.security import UNUSABLE_PASSWORD, hash_password, new_session_token, password_problems, token_digest
from app.services import RuleViolation

TTL = {"invite": timedelta(days=3), "reset": timedelta(hours=24)}
# The token travels in the URL fragment, which browsers never send to the server,
# so it does not end up in access logs or Referer headers.
LINK_PATH = "/set-password#token="


def has_password(user: User) -> bool:
    return user.password_hash != UNUSABLE_PASSWORD


def issue_link(db: Session, user: User, actor_id: str | None) -> dict:
    purpose = "reset" if has_password(user) else "invite"
    db.execute(delete(PasswordToken).where(PasswordToken.user_id == user.id, PasswordToken.used_at.is_(None)))
    token = new_session_token()
    expires_at = utcnow() + TTL[purpose]
    db.add(PasswordToken(user_id=user.id, token_digest=token_digest(token), purpose=purpose,
                         expires_at=expires_at, created_by=actor_id))
    db.flush()
    return {"path": LINK_PATH + token, "purpose": purpose, "expires_at": expires_at.isoformat()}


def find_link(db: Session, token: str) -> PasswordToken:
    row = db.scalar(select(PasswordToken).where(PasswordToken.token_digest == token_digest(token)))
    if row is None or row.used_at is not None or row.expires_at <= utcnow() or not row.user.is_active:
        raise RuleViolation("This link is invalid, expired or already used. Ask your administrator for a new one.", 410)
    return row


def set_password(db: Session, user: User, password: str) -> None:
    problems = password_problems(password, user.email)
    if problems:
        raise RuleViolation(problems)
    user.password_hash = hash_password(password)
    revoke_sessions(db, user)


def revoke_sessions(db: Session, user: User) -> None:
    for s in db.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))):
        s.revoked_at = utcnow()
