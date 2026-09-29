"""Business rules. Every function runs inside the caller's transaction."""

import hashlib
import json
import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crypto
from app.ai import AIConfig, server_config
from app.ai.base import ExtractionError, ExtractionResult
from app.ai.schema import SCHEMA_VERSION
from app.config import get_settings
from app.db import utcnow
from app.models import Decision, Draft, Extraction, Job, SearchRequest, SourceDocument, User, UserAISettings
from app.search.automation import AUTOMATED_SOURCES, automation_configured


class RuleViolation(Exception):
    """A business rule refused the action. `errors` is shown to the user."""

    def __init__(self, errors: list[str] | str, status_code: int = 422):
        self.errors = [errors] if isinstance(errors, str) else errors
        self.status_code = status_code
        super().__init__("; ".join(self.errors))


EDITABLE_STATUSES = {"Draft created", "Requires correction", "Pending pharmacist approval"}
FINAL_STATUSES = {"Approved", "Rejected"}

MANDATORY_FIELDS = [
    ("active_ingredient", "Active ingredient"),
    ("proposed_formula_name", "Proposed formula name"),
    ("strength", "Strength"),
    ("dosage_form", "Dosage form"),
    ("final_quantity", "Final quantity"),
    ("ingredients", "Ingredients"),
    ("preparation_method", "Preparation method"),
    ("packaging", "Packaging"),
    ("storage_conditions", "Storage conditions"),
    ("bud", "BUD"),
    ("labelling_instructions", "Labelling instructions"),
    ("warnings", "Warnings"),
]


def _reference(prefix: str) -> str:
    return f"{prefix}-{utcnow().year}-{secrets.token_hex(3).upper()}"


def content_hash(content: dict[str, Any]) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- requests


def create_request(db: Session, user: User, data: dict[str, Any]) -> SearchRequest:
    sources = list(dict.fromkeys(data.get("sources") or []))
    req = SearchRequest(
        number=_reference("MF"),
        active_ingredient=data["active_ingredient"].strip(),
        strength=(data.get("strength") or "").strip(),
        dosage_form=(data.get("dosage_form") or "").strip(),
        final_quantity=(data.get("final_quantity") or "").strip(),
        notes=(data.get("notes") or "").strip(),
        exact_match_only=bool(data.get("exact_match_only")),
        sources=sources,
        catalog_ref=data.get("catalog_ref"),
        created_by=user.id,
    )
    db.add(req)
    db.flush()
    settings = get_settings()
    if automation_configured(settings):
        for source in sources:
            if source in AUTOMATED_SOURCES:
                enqueue(db, Job(kind="search", request_id=req.id, source_name=source))
    refresh_request_status(db, req.id)
    return req


def enqueue(db: Session, job: Job) -> Job:
    job.max_attempts = get_settings().job_max_attempts
    db.add(job)
    db.flush()
    return job


def derive_request_status(req: SearchRequest) -> str:
    drafts = list(req.drafts)
    if drafts:
        latest = max(drafts, key=lambda d: (d.version, d.created_at))
        return latest.status
    search_jobs = [j for j in req.jobs if j.kind == "search"]
    if any(j.status in ("Queued", "Running") for j in search_jobs):
        return "Searching"
    if req.documents:
        return "Formula found"
    if search_jobs:
        if any(j.status in ("Failed", "Cooldown") for j in search_jobs):
            return "Error"
        if all(j.status in ("No results", "Cancelled") for j in search_jobs):
            return "No formula found"
    return "New"


def refresh_request_status(db: Session, request_id: str) -> str:
    db.flush()
    req = db.get(SearchRequest, request_id)
    db.refresh(req, ["jobs", "documents", "drafts"])
    req.status = derive_request_status(req)
    return req.status


def retry_search(db: Session, req: SearchRequest, source_name: str) -> Job:
    if source_name not in AUTOMATED_SOURCES:
        raise RuleViolation(f"{source_name} has no automated search; upload the PDF instead.")
    if not automation_configured(get_settings()):
        raise RuleViolation("Automated search is not configured on this server.")
    if any(j.kind == "search" and j.source_name == source_name and j.status in ("Queued", "Running") for j in req.jobs):
        raise RuleViolation("A search for this source is already running.", 409)
    job = enqueue(db, Job(kind="search", request_id=req.id, source_name=source_name))
    refresh_request_status(db, req.id)
    return job


def cancel_job(db: Session, job: Job) -> None:
    if job.status not in ("Queued", "Running"):
        raise RuleViolation("Only queued or running jobs can be cancelled.", 409)
    job.status = "Cancelled"
    job.finished_at = utcnow()
    job.lease_expires_at = None
    refresh_request_status(db, job.request_id)


# ---------------------------------------------------------------- extraction


def ai_identity_for(db: Session, user_id: str | None) -> tuple[str, str] | None:
    """(provider, model) that extraction for this user runs with, or None when AI
    is off for them. Does not touch the stored key."""
    row = db.get(UserAISettings, user_id) if user_id else None
    if row is None:
        config = server_config(get_settings())
        return (config.provider, config.model) if config else None
    if row.provider == "none" or not row.model:
        return None
    return row.provider, row.model


def ai_config_for(db: Session, user_id: str | None) -> AIConfig | None:
    """Like ai_identity_for, plus the decrypted API key. Raises ExtractionError
    when the stored key cannot be read."""
    row = db.get(UserAISettings, user_id) if user_id else None
    if row is None:
        return server_config(get_settings())
    if row.provider == "none" or not row.model:
        return None
    try:
        key = crypto.decrypt(row.api_key_encrypted) if row.api_key_encrypted else None
    except crypto.SecretError as exc:
        raise ExtractionError(str(exc)) from exc
    if not key:
        raise ExtractionError("No API key is saved for your AI provider. Add one in Account settings.")
    return AIConfig(row.provider, row.model, key)


def cached_extraction(db: Session, sha: str, provider: str, model: str) -> Extraction | None:
    return db.scalar(
        select(Extraction).where(
            Extraction.file_sha256 == sha,
            Extraction.provider == provider,
            Extraction.model == model,
            Extraction.schema_version == SCHEMA_VERSION,
        )
    )


def save_extraction(db: Session, sha: str, provider: str, model: str, result: ExtractionResult) -> Extraction:
    existing = cached_extraction(db, sha, provider, model)
    if existing:
        return existing
    ext = Extraction(
        file_sha256=sha,
        provider=provider,
        model=model,
        schema_version=SCHEMA_VERSION,
        output=result.output,
        usage={**result.usage, "served_model": result.model},
    )
    db.add(ext)
    db.flush()
    return ext


def extraction_for(db: Session, doc: SourceDocument) -> Extraction | None:
    """Latest extraction of this file by any provider: users may use different
    providers, and everyone working on the draft sees the same result."""
    if not doc.file_sha256:
        return None
    return db.scalar(
        select(Extraction)
        .where(Extraction.file_sha256 == doc.file_sha256, Extraction.schema_version == SCHEMA_VERSION)
        .order_by(Extraction.created_at.desc())
        .limit(1)
    )


def enqueue_extractions(db: Session, draft: Draft, user: User) -> list[Job]:
    """Queue extraction, with this user's AI settings, for each source document
    that has no cached result for that provider/model and no extraction already
    queued/running."""
    ident = ai_identity_for(db, user.id)
    if ident is None:
        return []
    jobs: list[Job] = []
    active = {
        j.source_document_id
        for j in db.scalars(
            select(Job).where(
                Job.kind == "extract",
                Job.source_document_id.in_(draft.source_document_ids),
                Job.status.in_(("Queued", "Running")),
            )
        )
    }
    for doc_id in draft.source_document_ids:
        doc = db.get(SourceDocument, doc_id)
        if doc is None or doc_id in active or not doc.file_sha256:
            continue
        if cached_extraction(db, doc.file_sha256, *ident) is not None:
            continue
        jobs.append(enqueue(db, Job(kind="extract", request_id=draft.request_id, source_document_id=doc_id,
                                    requested_by=user.id)))
    return jobs


# ---------------------------------------------------------------- drafts


def create_draft(db: Session, user: User, req: SearchRequest, document_ids: list[str]) -> Draft:
    docs = [db.get(SourceDocument, i) for i in dict.fromkeys(document_ids)]
    if not docs or any(d is None or d.request_id != req.id or not d.file_sha256 for d in docs):
        raise RuleViolation("Select at least one source PDF from this request.")
    draft = Draft(
        number=_reference("DRAFT"),
        request_id=req.id,
        version=1,
        status="Draft created",
        content={
            "active_ingredient": req.active_ingredient,
            "strength": req.strength,
            "dosage_form": req.dosage_form,
            "final_quantity": req.final_quantity,
            "active_ingredients": [],
        },
        source_document_ids=[d.id for d in docs],
        created_by=user.id,
    )
    db.add(draft)
    db.flush()
    enqueue_extractions(db, draft, user)
    refresh_request_status(db, req.id)
    return draft


def _check_version(draft: Draft, row_version: int) -> None:
    if draft.row_version != row_version:
        raise RuleViolation(
            "This draft was changed by someone else. Reload to see the latest version.", 409
        )


def save_draft(db: Session, draft: Draft, content: dict[str, Any], row_version: int) -> Draft:
    if draft.status not in EDITABLE_STATUSES:
        raise RuleViolation("Approved or rejected drafts are locked. Create a new revision instead.", 409)
    _check_version(draft, row_version)
    draft.content = content
    draft.row_version += 1
    if draft.status == "Pending pharmacist approval":
        # Content changed after submission: it must be re-submitted, so the
        # pharmacist always approves exactly what was submitted.
        draft.status = "Draft created"
        draft.submitted_by = None
        draft.submitted_at = None
    refresh_request_status(db, draft.request_id)
    return draft


def approval_errors(draft: Draft) -> list[str]:
    c = draft.content or {}
    errors: list[str] = []
    missing = [label for key, label in MANDATORY_FIELDS if not str(c.get(key) or "").strip()]
    if missing:
        errors.append(f"Mandatory fields missing: {', '.join(missing)}.")
    ais = c.get("active_ingredients") or []
    included = [a for a in ais if a.get("included_in_local_formula", True) is not False]
    excluded = [a for a in ais if a.get("included_in_local_formula", True) is False]
    if not included:
        errors.append("At least one active ingredient must be included.")
    for a in included:
        name = a.get("ingredient_name") or a.get("name") or "?"
        if not str(a.get("strength_value") or "").strip():
            errors.append(f'Active ingredient "{name}" requires a strength value.')
        if not str(a.get("quantity_value") or "").strip():
            errors.append(f'Active ingredient "{name}" requires a quantity value.')
    for a in excluded:
        name = a.get("ingredient_name") or a.get("name") or "?"
        if not str(a.get("exclusion_reason") or "").strip():
            errors.append(f'Excluded active ingredient "{name}" requires an exclusion reason.')
    if not draft.source_document_ids:
        errors.append("At least one source formula must be attached.")
    return errors


def submit_draft(db: Session, user: User, draft: Draft, row_version: int) -> Draft:
    if draft.status not in ("Draft created", "Requires correction"):
        raise RuleViolation("Only drafts in preparation can be submitted.", 409)
    _check_version(draft, row_version)
    errors = approval_errors(draft)
    if errors:
        raise RuleViolation(errors)
    draft.status = "Pending pharmacist approval"
    draft.submitted_by = user.id
    draft.submitted_at = utcnow()
    draft.row_version += 1
    refresh_request_status(db, draft.request_id)
    return draft


def decide(
    db: Session, user: User, draft: Draft, decision: str, notes: str, seen_content_sha256: str
) -> Decision:
    if decision not in ("approved", "rejected", "returned"):
        raise RuleViolation("Unknown decision.")
    if draft.status != "Pending pharmacist approval":
        raise RuleViolation("Only drafts pending approval can be decided.", 409)
    current = content_hash(draft.content)
    if seen_content_sha256 != current:
        raise RuleViolation("The draft changed since you opened it. Reload and review again.", 409)
    if draft.submitted_by == user.id:
        raise RuleViolation("The pharmacist who approves must be different from the person who submitted.", 403)
    if decision in ("rejected", "returned") and not notes.strip():
        raise RuleViolation("A review note is required to reject or return a draft.")
    if decision == "approved":
        if not (user.licence_number or "").strip():
            raise RuleViolation("Your user profile has no pharmacist licence number. Ask an admin to add it.", 403)
        errors = approval_errors(draft)
        if errors:
            raise RuleViolation(errors)

    preparer = db.get(User, draft.submitted_by) if draft.submitted_by else None
    row = Decision(
        draft_id=draft.id,
        decision=decision,
        actor_id=user.id,
        actor_name=user.full_name,
        actor_licence=user.licence_number,
        preparer_id=preparer.id if preparer else None,
        preparer_name=preparer.full_name if preparer else None,
        preparer_licence=preparer.licence_number if preparer else None,
        notes=notes.strip(),
        content_sha256=current,
    )
    db.add(row)
    draft.status = {"approved": "Approved", "rejected": "Rejected", "returned": "Requires correction"}[decision]
    draft.row_version += 1
    db.flush()
    refresh_request_status(db, draft.request_id)
    return row


def new_revision(db: Session, user: User, draft: Draft) -> Draft:
    if draft.status != "Approved":
        raise RuleViolation("Only approved formulas can be revised.", 409)
    newer = db.scalar(select(Draft).where(Draft.predecessor_id == draft.id))
    if newer is not None:
        raise RuleViolation("A newer revision already exists.", 409)
    rev = Draft(
        number=_reference("DRAFT"),
        request_id=draft.request_id,
        version=draft.version + 1,
        predecessor_id=draft.id,
        status="Draft created",
        content={**draft.content, "revision_change_notes": ""},
        source_document_ids=list(draft.source_document_ids),
        created_by=user.id,
    )
    db.add(rev)
    db.flush()
    refresh_request_status(db, draft.request_id)
    return rev


def archive(db: Session, draft: Draft) -> None:
    if draft.status != "Approved":
        raise RuleViolation("Only approved formulas can be archived.", 409)
    if draft.archived_at is None:
        draft.archived_at = utcnow()


def approval_of(draft: Draft) -> Decision | None:
    approved = [d for d in draft.decisions if d.decision == "approved"]
    return approved[-1] if approved else None


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
