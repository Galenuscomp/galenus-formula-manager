"""Encryption at rest for secrets users store (their AI provider API keys).

The Fernet key is derived from SECRETS_KEY, which lives only in .env, so a copy
of the database alone does not reveal the stored keys.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class SecretError(Exception):
    pass


def _fernet() -> Fernet:
    secret = get_settings().secrets_key
    if not secret:
        raise SecretError("SECRETS_KEY is not set on this server, so API keys cannot be stored.")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest()))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretError("The saved API key can no longer be read. Enter it again in Account settings.") from exc
