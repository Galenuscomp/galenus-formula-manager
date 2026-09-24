from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent


def record(db: Session, actor_id: str | None, action: str, entity: str, entity_id: str, **detail: Any) -> None:
    db.add(AuditEvent(actor_id=actor_id, action=action, entity=entity, entity_id=entity_id, detail=detail))
