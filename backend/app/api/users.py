from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app import audit
from app.api import serialize
from app.api.deps import DB, Admin
from app.api.schemas import UserCreateIn, UserUpdateIn
from app.db import utcnow
from app.models import AuthSession, User
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
def list_users(_: Admin, db: DB):
    return [serialize.user(u) for u in db.scalars(select(User).order_by(User.full_name))]


@router.post("", status_code=201)
def create_user(body: UserCreateIn, actor: Admin, db: DB):
    email = body.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "A user with this e-mail already exists")
    user = User(
        email=email,
        full_name=body.full_name.strip(),
        role=body.role,
        licence_number=(body.licence_number or "").strip() or None,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.flush()
    audit.record(db, actor.id, "user_created", "user", user.id, role=user.role)
    db.commit()
    return serialize.user(user)


@router.patch("/{user_id}")
def update_user(user_id: str, body: UserUpdateIn, actor: Admin, db: DB):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    changes = body.model_dump(exclude_unset=True)
    if user.id == actor.id and (changes.get("role", "admin") != "admin" or changes.get("is_active") is False):
        raise HTTPException(400, "You cannot demote or disable your own account")
    revoke = False
    for key, value in changes.items():
        if key == "password":
            user.password_hash = hash_password(value)
            revoke = True
        elif key == "licence_number":
            user.licence_number = (value or "").strip() or None
        else:
            setattr(user, key, value)
    if revoke or changes.get("is_active") is False or "role" in changes:
        for s in db.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))):
            s.revoked_at = utcnow()
    audit.record(db, actor.id, "user_updated", "user", user.id, fields=sorted(k for k in changes if k != "password"))
    db.commit()
    return serialize.user(user)
