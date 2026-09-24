import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()
# Verified against when the e-mail is unknown so response timing does not reveal
# which accounts exist.
_DUMMY_HASH = _hasher.hash("not-a-real-password")

ROLES = ("admin", "pharmacist", "technician")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    """Only digests are stored, so a database leak does not leak live sessions."""
    return hashlib.sha256(token.encode()).hexdigest()


def can_prepare(role: str) -> bool:
    return role in ("pharmacist", "technician")


def can_approve(role: str) -> bool:
    return role == "pharmacist"
