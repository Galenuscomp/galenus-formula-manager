from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, or_, select

from app import audit, services
from app.api import serialize
from app.api.deps import DB, CurrentUser, Pharmacist, Preparer
from app.api.schemas import (
    DecisionIn,
    DraftCreateIn,
    DraftSaveIn,
    RequestCreateIn,
    RetrySearchIn,
    RowVersionIn,
    SourceUpdateIn,
)
from app.config import get_settings
from app.models import Draft, Job, SearchRequest, SourceDocument
from app.pdf import render_formula_pdf
from app.search.automation import AUTOMATED_SOURCES, automation_configured
from app.services import RuleViolation
from app.storage import InvalidFile, read_pdf, store_pdf

router = APIRouter(prefix="/api", tags=["formulas"])


def _get(db, model, id_: str):
    obj = db.get(model, id_)
    if obj is None:
        raise HTTPException(404, f"{model.__name__} not found")
    return obj


def _commit(db):
    db.commit()


# ------------------------------------------------------------------ meta


@router.get("/config")
def app_config(user: CurrentUser, db: DB):
    s = get_settings()
    ident = services.ai_identity_for(db, user.id)
    return {
        "automated_sources": sorted(AUTOMATED_SOURCES) if automation_configured(s) else [],
        "ai_enabled": ident is not None,
        "ai_provider": ident[0] if ident else "none",
        "max_upload_mb": s.max_upload_mb,
    }


@router.get("/dashboard")
def dashboard(_: CurrentUser, db: DB):
    counts = dict(db.execute(select(SearchRequest.status, func.count()).group_by(SearchRequest.status)).all())
    approved_count = db.scalar(
        select(func.count()).select_from(Draft).where(Draft.status == "Approved", Draft.archived_at.is_(None))
    )
    recent = db.scalars(select(SearchRequest).order_by(SearchRequest.created_at.desc()).limit(5)).all()
    return {
        "total_requests": sum(counts.values()),
        "in_progress": sum(counts.get(s, 0) for s in ("Searching", "Draft created", "Pending pharmacist approval",
                                                         "Requires correction", "Formula found")),
        "pending_approval": counts.get("Pending pharmacist approval", 0),
        "approved_formulas": approved_count or 0,
        "recent_requests": [serialize.request_summary(r) for r in recent],
    }


# ------------------------------------------------------------------ requests


@router.get("/requests")
def list_requests(
    _: CurrentUser,
    db: DB,
    q: str = "",
    status: str = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(SearchRequest)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                SearchRequest.active_ingredient.ilike(like),
                SearchRequest.number.ilike(like),
                SearchRequest.dosage_form.ilike(like),
            )
        )
    if status:
        stmt = stmt.where(SearchRequest.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(SearchRequest.created_at.desc()).limit(limit).offset(offset)).all()
    return {"total": total, "items": [serialize.request_summary(r) for r in rows]}


@router.post("/requests", status_code=201)
def create_request(body: RequestCreateIn, user: Preparer, db: DB):
    req = services.create_request(db, user, body.model_dump())
    audit.record(db, user.id, "request_created", "request", req.id)
    _commit(db)
    return serialize.request_summary(req)


@router.get("/requests/{request_id}")
def get_request(request_id: str, _: CurrentUser, db: DB):
    req = _get(db, SearchRequest, request_id)
    return {
        **serialize.request_summary(req),
        "jobs": [serialize.job(j) for j in req.jobs if j.kind == "search"],
        "documents": [serialize.document(d) for d in req.documents],
        "drafts": [serialize.draft_summary(d) for d in sorted(req.drafts, key=lambda d: d.created_at, reverse=True)],
    }


@router.post("/requests/{request_id}/search")
def retry_search(request_id: str, body: RetrySearchIn, user: Preparer, db: DB):
    req = _get(db, SearchRequest, request_id)
    job = services.retry_search(db, req, body.source_name)
    audit.record(db, user.id, "search_queued", "request", req.id, source=body.source_name)
    _commit(db)
    return serialize.job(job)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, user: Preparer, db: DB):
    job = _get(db, Job, job_id)
    services.cancel_job(db, job)
    audit.record(db, user.id, "job_cancelled", "job", job.id)
    _commit(db)
    return serialize.job(job)


@router.post("/requests/{request_id}/documents", status_code=201)
async def upload_document(
    request_id: str,
    user: Preparer,
    db: DB,
    file: Annotated[UploadFile, File()],
    source_name: Annotated[str, Form(max_length=120)],
    source_formula_id: Annotated[str, Form(max_length=200)] = "",
    title: Annotated[str, Form(max_length=500)] = "",
    source_url: Annotated[str, Form(max_length=2000)] = "",
    notes: Annotated[str, Form(max_length=5000)] = "",
    match_level: Annotated[str, Form(max_length=20)] = "",
):
    req = _get(db, SearchRequest, request_id)
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    try:
        sha, size = store_pdf(data)
    except InvalidFile as exc:
        raise HTTPException(400, str(exc)) from exc
    doc = SourceDocument(
        request_id=req.id,
        source_name=source_name.strip() or "Other",
        source_formula_id=source_formula_id.strip(),
        title=title.strip(),
        source_url=source_url.strip(),
        notes=notes.strip(),
        match_level=match_level if match_level in ("Exact", "Partial", "Alternative") else None,
        origin="upload",
        file_name=(file.filename or "source.pdf")[:300],
        file_sha256=sha,
        file_size=size,
        created_by=user.id,
    )
    db.add(doc)
    db.flush()
    services.refresh_request_status(db, req.id)
    audit.record(db, user.id, "document_uploaded", "document", doc.id, sha256=sha)
    _commit(db)
    return serialize.document(doc)


@router.patch("/documents/{doc_id}")
def update_document(doc_id: str, body: SourceUpdateIn, user: Preparer, db: DB):
    doc = _get(db, SourceDocument, doc_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(doc, key, value)
    _commit(db)
    return serialize.document(doc)


@router.get("/documents/{doc_id}/file")
def document_file(doc_id: str, _: CurrentUser, db: DB):
    doc = _get(db, SourceDocument, doc_id)
    if not doc.file_sha256:
        raise HTTPException(404, "No file")
    return Response(
        read_pdf(doc.file_sha256),
        media_type="application/pdf",
        headers={"Content-Disposition": "inline", "Cache-Control": "private, max-age=3600"},
    )


# ------------------------------------------------------------------ drafts


@router.post("/requests/{request_id}/drafts", status_code=201)
def create_draft(request_id: str, body: DraftCreateIn, user: Preparer, db: DB):
    req = _get(db, SearchRequest, request_id)
    draft = services.create_draft(db, user, req, body.source_document_ids)
    audit.record(db, user.id, "draft_created", "draft", draft.id)
    _commit(db)
    return serialize.draft_summary(draft)


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: str, user: CurrentUser, db: DB):
    return serialize.draft_detail(db, _get(db, Draft, draft_id), user)


@router.put("/drafts/{draft_id}")
def save_draft(draft_id: str, body: DraftSaveIn, user: Preparer, db: DB):
    draft = _get(db, Draft, draft_id)
    services.save_draft(db, draft, body.content.model_dump(), body.row_version)
    audit.record(db, user.id, "draft_saved", "draft", draft.id, row_version=draft.row_version)
    _commit(db)
    return serialize.draft_detail(db, draft, user)


@router.post("/drafts/{draft_id}/extract")
def extract(draft_id: str, user: Preparer, db: DB):
    draft = _get(db, Draft, draft_id)
    if services.ai_identity_for(db, user.id) is None:
        raise RuleViolation("AI extraction is turned off for your account. Choose a provider in Account settings.")
    jobs = services.enqueue_extractions(db, draft, user)
    audit.record(db, user.id, "extraction_queued", "draft", draft.id, jobs=len(jobs))
    _commit(db)
    return {"queued": len(jobs)}


@router.post("/drafts/{draft_id}/submit")
def submit(draft_id: str, body: RowVersionIn, user: Preparer, db: DB):
    draft = _get(db, Draft, draft_id)
    services.submit_draft(db, user, draft, body.row_version)
    audit.record(db, user.id, "draft_submitted", "draft", draft.id, content_sha256=services.content_hash(draft.content))
    _commit(db)
    return serialize.draft_detail(db, draft, user)


@router.post("/drafts/{draft_id}/decision")
def decide(draft_id: str, body: DecisionIn, user: Pharmacist, db: DB):
    draft = _get(db, Draft, draft_id)
    decision = services.decide(db, user, draft, body.decision, body.notes, body.content_sha256)
    if decision.decision == "approved":
        docs = [d for d in (db.get(SourceDocument, i) for i in draft.source_document_ids) if d]
        pdf = render_formula_pdf(draft, draft.request, docs, decision, decision.content_sha256)
        sha, _ = store_pdf(pdf)
        decision.pdf_sha256 = sha
    audit.record(db, user.id, f"draft_{decision.decision}", "draft", draft.id, content_sha256=decision.content_sha256)
    _commit(db)
    db.refresh(draft)
    return serialize.draft_detail(db, draft, user)


@router.post("/drafts/{draft_id}/revise", status_code=201)
def revise(draft_id: str, user: Preparer, db: DB):
    draft = _get(db, Draft, draft_id)
    rev = services.new_revision(db, user, draft)
    audit.record(db, user.id, "revision_created", "draft", rev.id, predecessor=draft.id)
    _commit(db)
    return serialize.draft_summary(rev)


@router.post("/drafts/{draft_id}/archive")
def archive(draft_id: str, user: Pharmacist, db: DB):
    draft = _get(db, Draft, draft_id)
    services.archive(db, draft)
    audit.record(db, user.id, "formula_archived", "draft", draft.id)
    _commit(db)
    return serialize.draft_summary(draft)


@router.get("/drafts/{draft_id}/pdf")
def draft_pdf(draft_id: str, _: CurrentUser, db: DB):
    draft = _get(db, Draft, draft_id)
    approval = services.approval_of(draft)
    if approval and approval.pdf_sha256:
        data = read_pdf(approval.pdf_sha256)
    else:
        docs = [d for d in (db.get(SourceDocument, i) for i in draft.source_document_ids) if d]
        data = render_formula_pdf(draft, draft.request, docs, None, services.content_hash(draft.content))
    name = f"{draft.number}-v{draft.version}.pdf"
    return Response(
        data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}"'}
    )


@router.get("/library")
def library(
    _: CurrentUser,
    db: DB,
    q: str = "",
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(Draft).where(Draft.status == "Approved")
    if not include_archived:
        stmt = stmt.where(Draft.archived_at.is_(None))
    rows = db.scalars(stmt.order_by(Draft.updated_at.desc())).all()
    if q.strip():
        needle = q.strip().lower()
        rows = [
            d for d in rows
            if needle in " ".join(
                str((d.content or {}).get(k, "")) for k in ("proposed_formula_name", "active_ingredient", "dosage_form")
            ).lower() or needle in d.number.lower()
        ]
    superseded = {
        d.predecessor_id for d in db.scalars(select(Draft).where(Draft.status == "Approved", Draft.predecessor_id.is_not(None)))
    }
    items = [dict(serialize.draft_summary(d), superseded=d.id in superseded) for d in rows]
    return {"total": len(items), "items": items[offset : offset + limit]}
