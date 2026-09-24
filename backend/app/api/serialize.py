from typing import Any

from sqlalchemy.orm import Session

from app import services
from app.models import Decision, Draft, Job, SearchRequest, SourceDocument, User
from app.services import iso


def user(u: User) -> dict[str, Any]:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "licence_number": u.licence_number,
        "is_active": u.is_active,
    }


def request_summary(r: SearchRequest) -> dict[str, Any]:
    return {
        "id": r.id,
        "number": r.number,
        "active_ingredient": r.active_ingredient,
        "strength": r.strength,
        "dosage_form": r.dosage_form,
        "final_quantity": r.final_quantity,
        "notes": r.notes,
        "exact_match_only": r.exact_match_only,
        "sources": r.sources,
        "status": r.status,
        "created_at": iso(r.created_at),
    }


def job(j: Job) -> dict[str, Any]:
    return {
        "id": j.id,
        "kind": j.kind,
        "source_name": j.source_name,
        "source_document_id": j.source_document_id,
        "status": j.status,
        "attempts": j.attempts,
        "max_attempts": j.max_attempts,
        "error": j.error,
        "created_at": iso(j.created_at),
        "started_at": iso(j.started_at),
        "finished_at": iso(j.finished_at),
    }


def document(d: SourceDocument) -> dict[str, Any]:
    return {
        "id": d.id,
        "request_id": d.request_id,
        "source_name": d.source_name,
        "source_formula_id": d.source_formula_id,
        "title": d.title,
        "source_url": d.source_url,
        "notes": d.notes,
        "match_level": d.match_level,
        "origin": d.origin,
        "file_name": d.file_name,
        "file_sha256": d.file_sha256,
        "file_size": d.file_size,
        "has_file": bool(d.file_sha256),
        "selected": d.selected,
        "retrieved_at": iso(d.retrieved_at),
    }


def decision(d: Decision) -> dict[str, Any]:
    return {
        "id": d.id,
        "decision": d.decision,
        "actor_name": d.actor_name,
        "actor_licence": d.actor_licence,
        "preparer_name": d.preparer_name,
        "preparer_licence": d.preparer_licence,
        "notes": d.notes,
        "content_sha256": d.content_sha256,
        "pdf_sha256": d.pdf_sha256,
        "created_at": iso(d.created_at),
    }


def draft_summary(d: Draft) -> dict[str, Any]:
    approval = services.approval_of(d)
    return {
        "id": d.id,
        "number": d.number,
        "request_id": d.request_id,
        "version": d.version,
        "predecessor_id": d.predecessor_id,
        "status": d.status,
        "proposed_formula_name": (d.content or {}).get("proposed_formula_name", ""),
        "active_ingredient": (d.content or {}).get("active_ingredient", ""),
        "strength": (d.content or {}).get("strength", ""),
        "dosage_form": (d.content or {}).get("dosage_form", ""),
        "archived_at": iso(d.archived_at),
        "created_at": iso(d.created_at),
        "updated_at": iso(d.updated_at),
        "approval": decision(approval) if approval else None,
    }


def draft_detail(db: Session, d: Draft, viewer: User) -> dict[str, Any]:
    docs = [db.get(SourceDocument, i) for i in d.source_document_ids]
    docs = [x for x in docs if x is not None]
    extractions = {}
    for doc in docs:
        ext = services.extraction_for(db, doc)
        if ext is not None:
            extractions[doc.id] = {"output": ext.output, "provider": ext.provider, "model": ext.model,
                                   "created_at": iso(ext.created_at)}
    jobs = [j for j in d.request.jobs if j.kind == "extract" and j.source_document_id in d.source_document_ids]
    submitter = db.get(User, d.submitted_by) if d.submitted_by else None
    revisions = sorted(d.request.drafts, key=lambda x: (x.version, x.created_at), reverse=True)
    return {
        **draft_summary(d),
        "content": d.content,
        "content_sha256": services.content_hash(d.content),
        "row_version": d.row_version,
        "source_document_ids": d.source_document_ids,
        "submitted_by": {"id": submitter.id, "full_name": submitter.full_name} if submitter else None,
        "submitted_at": iso(d.submitted_at),
        "request": request_summary(d.request),
        "documents": [document(x) for x in docs],
        "extractions": extractions,
        "extraction_jobs": [job(j) for j in jobs],
        "decisions": [decision(x) for x in d.decisions],
        "revisions": [draft_summary(x) for x in revisions],
        "approval_errors": services.approval_errors(d),
        "permissions": {
            "can_edit": d.status in services.EDITABLE_STATUSES and viewer.role in ("pharmacist", "technician"),
            "can_submit": d.status in ("Draft created", "Requires correction")
            and viewer.role in ("pharmacist", "technician"),
            "can_decide": d.status == "Pending pharmacist approval"
            and viewer.role == "pharmacist"
            and d.submitted_by != viewer.id,
            "can_revise": d.status == "Approved" and viewer.role in ("pharmacist", "technician"),
        },
    }
