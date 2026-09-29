from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app import audit, passwords
from app.api import serialize
from app.api.deps import DB, Admin
from app.api.schemas import UserCreateIn, UserUpdateIn
from app.models import User, UserAISettings
from app.security import UNUSABLE_PASSWORD, hash_password, password_problems
from app.services import RuleViolation

router = APIRouter(prefix="/api/users", tags=["users"])


def _admin_view(u: User, ai_provider: str) -> dict:
    return {**serialize.user(u), "ai_provider": ai_provider, "has_password": passwords.has_password(u)}


@router.get("")
def list_users(_: Admin, db: DB):
    # Which AI provider each user extracts with; the admin never sees their keys.
    ai = {r.user_id: r.provider for r in db.scalars(select(UserAISettings))}
    return [_admin_view(u, ai.get(u.id, "default")) for u in db.scalars(select(User).order_by(User.full_name))]


@router.post("", status_code=201)
def create_user(body: UserCreateIn, actor: Admin, db: DB):
    email = body.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "A user with this e-mail already exists")
    if body.password is not None:
        problems = password_problems(body.password, email)
        if problems:
            raise RuleViolation(problems)
    user = User(
        email=email,
        full_name=body.full_name.strip(),
        role=body.role,
        licence_number=(body.licence_number or "").strip() or None,
        password_hash=hash_password(body.password) if body.password is not None else UNUSABLE_PASSWORD,
    )
    db.add(user)
    db.flush()
    link = passwords.issue_link(db, user, actor.id) if body.password is None else None
    audit.record(db, actor.id, "user_created", "user", user.id, role=user.role, invited=link is not None)
    db.commit()
    return {**_admin_view(user, "default"), "password_link": link}


@router.patch("/{user_id}")
def update_user(user_id: str, body: UserUpdateIn, actor: Admin, db: DB):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    changes = body.model_dump(exclude_unset=True)
    if user.id == actor.id and (changes.get("role", "admin") != "admin" or changes.get("is_active") is False):
        raise HTTPException(400, "You cannot demote or disable your own account")
    if "email" in changes:
        changes["email"] = changes["email"].strip().lower()
        if changes["email"] != user.email and db.scalar(select(User).where(User.email == changes["email"])):
            raise HTTPException(409, "A user with this e-mail already exists")
    for key, value in changes.items():
        if key == "password":
            passwords.set_password(db, user, value)
        elif key == "licence_number":
            user.licence_number = (value or "").strip() or None
        else:
            setattr(user, key, value)
    if changes.get("is_active") is False or "role" in changes:
        passwords.revoke_sessions(db, user)
    audit.record(db, actor.id, "user_updated", "user", user.id, fields=sorted(k for k in changes if k != "password"))
    db.commit()
    return {**serialize.user(user), "has_password": passwords.has_password(user)}


@router.post("/{user_id}/password-link")
def create_password_link(user_id: str, actor: Admin, db: DB):
    """One-time link for the user to choose a new password (or their first one)."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if not user.is_active:
        raise RuleViolation("This account is disabled. Enable it first.")
    link = passwords.issue_link(db, user, actor.id)
    audit.record(db, actor.id, f"password_{link['purpose']}_link_created", "user", user.id)
    db.commit()
    return link
