import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()
# Verified against when the e-mail is unknown so response timing does not reveal
# which accounts exist.
_DUMMY_HASH = _hasher.hash("not-a-real-password")

ROLES = ("admin", "pharmacist", "technician")

# Stored for invited users who have not chosen a password yet: never verifies.
UNUSABLE_PASSWORD = "!"
PASSWORD_MIN_LENGTH = 10


def password_problems(password: str, email: str | None = None) -> list[str]:
    """Rules for a new password, as messages for the user. The frontend shows the
    same rules as a checklist (frontend/src/lib/passwordRules.js)."""
    problems = []
    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(f"Use at least {PASSWORD_MIN_LENGTH} characters.")
    if not any(c.isalpha() for c in password):
        problems.append("Include at least one letter.")
    if not any(c.isdigit() for c in password):
        problems.append("Include at least one digit.")
    local = (email or "").split("@")[0].lower()
    if len(local) >= 3 and local in password.lower():
        problems.append("Do not use your e-mail address in the password.")
    return problems


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
