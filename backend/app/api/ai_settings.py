"""Each user's own AI extraction provider (Account settings).

The API key is verified with the provider before it is saved, stored encrypted,
and never returned: responses only carry its last four characters.
"""

from typing import Any

from fastapi import APIRouter

from app import audit, crypto, services
from app.ai import AIConfig, get_extractor, server_config
from app.ai.base import ExtractionError
from app.api.deps import DB, CurrentUser
from app.api.schemas import AISettingsIn
from app.config import get_settings
from app.models import User, UserAISettings
from app.services import RuleViolation

router = APIRouter(prefix="/api/account/ai", tags=["account"])

# Suggestions for the model field; any model name the provider accepts can be saved.
SUGGESTED_MODELS = {
    "openai": ["gpt-6.1-sol", "gpt-6-luna", "gpt-6-astra"],
    "anthropic": ["claude-opus-5", "claude-sonnet-5-5", "claude-haiku-4-5"],
}


def _view(db, user: User) -> dict[str, Any]:
    row = db.get(UserAISettings, user.id)
    server = server_config(get_settings())
    return {
        "provider": row.provider if row else "default",
        "model": row.model if row else None,
        "key_last4": row.key_last4 if row else None,
        "server_default": {"provider": server.provider, "model": server.model} if server else None,
        "suggested_models": SUGGESTED_MODELS,
        "can_store_keys": bool(get_settings().secrets_key),
    }


def _verify(config: AIConfig) -> None:
    try:
        get_extractor(config, get_settings()).verify()
    except ExtractionError as exc:
        raise RuleViolation(str(exc)) from exc


@router.get("")
def get_ai_settings(user: CurrentUser, db: DB):
    return _view(db, user)


@router.put("")
def save_ai_settings(body: AISettingsIn, user: CurrentUser, db: DB):
    row = db.get(UserAISettings, user.id)
    if body.provider == "default":
        if row is not None:
            db.delete(row)
    elif body.provider == "none":
        row = row or UserAISettings(user_id=user.id)
        row.provider, row.model, row.api_key_encrypted, row.key_last4 = "none", None, None, None
        db.add(row)
    else:
        model = (body.model or "").strip()
        if not model:
            raise RuleViolation("Choose a model.")
        key = (body.api_key or "").strip()
        try:
            if not key and row is not None and row.provider == body.provider and row.api_key_encrypted:
                key = crypto.decrypt(row.api_key_encrypted)
            if not key:
                raise RuleViolation("Enter an API key.")
            _verify(AIConfig(body.provider, model, key))
            encrypted = crypto.encrypt(key)
        except crypto.SecretError as exc:
            raise RuleViolation(str(exc)) from exc
        row = row or UserAISettings(user_id=user.id)
        row.provider, row.model, row.api_key_encrypted, row.key_last4 = body.provider, model, encrypted, key[-4:]
        db.add(row)
    audit.record(db, user.id, "ai_settings_changed", "user", user.id,
                 provider=body.provider, model=(body.model or "").strip() or None)
    db.commit()
    return _view(db, user)


@router.post("/test")
def test_ai_settings(user: CurrentUser, db: DB):
    try:
        config = services.ai_config_for(db, user.id)
    except ExtractionError as exc:
        raise RuleViolation(str(exc)) from exc
    if config is None:
        raise RuleViolation("AI extraction is turned off for your account.")
    _verify(config)
    return {"ok": True, "provider": config.provider, "model": config.model}
