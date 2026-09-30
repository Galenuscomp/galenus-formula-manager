"""DB-backed job queue.

A job is claimed with a conditional UPDATE (status must still be Queued), so two
workers can never run the same job, on SQLite or PostgreSQL. A claimed job holds
a lease; if the worker dies, the lease expires and the job is retried or failed
instead of staying 'running' forever (the main cause of stuck searches before).
"""

import logging
from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app import services
from app.ai import ExtractionError, get_extractor
from app.config import get_settings
from app.db import utcnow
from app.models import Extraction, Job, SearchRequest, SourceDocument
from app.search.automation import SearchCooldown, SearchFailed, SearchNoResults
from app.search.automation import fetch as fetch_source
from app.storage import InvalidFile, read_pdf, store_pdf

log = logging.getLogger(__name__)

ACTIVE = ("Queued", "Running")
# Longer than CompoundingToday's 5-minute "Account in Use" lock, so a retry is not wasted.
COOLDOWN = timedelta(minutes=6)


def recover_expired_leases(db: Session) -> int:
    now = utcnow()
    stale = db.scalars(
        select(Job).where(Job.status == "Running", Job.lease_expires_at < now).with_for_update(skip_locked=True)
    ).all()
    for job in stale:
        if job.attempts >= job.max_attempts:
            _finish(db, job, "Failed", "Job timed out")
        else:
            job.status = "Queued"
            job.lease_expires_at = None
            job.error = "Previous attempt timed out; retrying"
            services.refresh_request_status(db, job.request_id)
    db.commit()
    return len(stale)


def claim_next(db: Session) -> Job | None:
    now = utcnow()
    candidates = db.scalars(
        select(Job.id)
        .where(Job.status == "Queued", or_(Job.run_after.is_(None), Job.run_after <= now))
        .order_by(Job.created_at)
        .limit(5)
    ).all()
    for job_id in candidates:
        result = db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == "Queued")
            .values(
                status="Running",
                attempts=Job.attempts + 1,
                started_at=now,
                lease_expires_at=now + timedelta(seconds=get_settings().job_lease_seconds),
                error=None,
            )
        )
        if result.rowcount == 1:
            db.commit()
            job = db.get(Job, job_id)
            db.refresh(job)
            services.refresh_request_status(db, job.request_id)
            db.commit()
            return job
        db.rollback()
    return None


def _finish(db: Session, job: Job, status: str, error: str | None = None) -> None:
    job.status = status
    job.error = error
    job.finished_at = utcnow()
    job.lease_expires_at = None
    services.refresh_request_status(db, job.request_id)


def _retry_or_fail(db: Session, job: Job, message: str, retryable: bool) -> None:
    if retryable and job.attempts < job.max_attempts:
        job.status = "Queued"
        job.error = message
        job.lease_expires_at = None
        job.run_after = utcnow() + timedelta(seconds=15 * 2 ** job.attempts)
        services.refresh_request_status(db, job.request_id)
    else:
        _finish(db, job, "Failed", message)


def run_job(db: Session, job: Job) -> None:
    try:
        if job.kind == "search":
            _run_search(db, job)
        elif job.kind == "extract":
            _run_extract(db, job)
        else:
            _finish(db, job, "Failed", f"Unknown job kind {job.kind}")
    except Exception:  # never leave a job running because of an unexpected bug
        log.exception("job %s crashed", job.id)
        db.rollback()
        job = db.get(Job, job.id)
        _finish(db, job, "Failed", "Unexpected error while running job")
    db.commit()


def _still_running(db: Session, job: Job) -> bool:
    db.refresh(job)
    return job.status == "Running"


def _run_search(db: Session, job: Job) -> None:
    request = db.get(SearchRequest, job.request_id)
    wanted = job.payload or {}
    try:
        found = fetch_source(
            db,
            job.source_name,
            user_id=job.requested_by,  # with the login of the user who asked for it
            active_ingredient=request.active_ingredient,
            strength=request.strength,
            dosage_form=request.dosage_form,
            formula_id=wanted.get("formula_id", ""),
            title=wanted.get("title", ""),
        )
    except SearchCooldown:
        if _still_running(db, job):
            if job.attempts < job.max_attempts:
                job.status = "Queued"
                job.run_after = utcnow() + COOLDOWN
                job.error = "Rate limited by source; retrying automatically"
                job.lease_expires_at = None
                services.refresh_request_status(db, job.request_id)
            else:
                _finish(db, job, "Cooldown", "Rate limited by source. Please retry shortly.")
        return
    except SearchNoResults:
        if _still_running(db, job):
            _finish(db, job, "No results")
        return
    except SearchFailed as exc:
        if _still_running(db, job):
            _retry_or_fail(db, job, str(exc), exc.retryable)
        return

    if not _still_running(db, job):  # cancelled while the worker was fetching
        return
    try:
        sha, size = store_pdf(found.pdf)
    except InvalidFile as exc:
        _finish(db, job, "Failed", str(exc))
        return
    if db.scalar(select(SourceDocument.id).where(SourceDocument.request_id == request.id,
                                                 SourceDocument.file_sha256 == sha)):
        _finish(db, job, "Completed")  # the same PDF is already on this request
        return
    db.add(
        SourceDocument(
            request_id=request.id,
            source_name=found.source_name,
            source_formula_id=found.source_formula_id,
            title=found.title,
            source_url=found.url,
            origin="automated",
            file_name=found.filename,
            file_sha256=sha,
            file_size=size,
        )
    )
    db.flush()
    _finish(db, job, "Completed")


def _run_extract(db: Session, job: Job) -> None:
    doc = db.get(SourceDocument, job.source_document_id)
    if doc is None or not doc.file_sha256:
        _finish(db, job, "Failed", "Source document has no file")
        return
    try:
        # Settings are read when the job runs, so a key fixed after a failure is used on retry.
        config = services.ai_config_for(db, job.requested_by)
        if config is None:
            raise ExtractionError("AI extraction is turned off for the user who requested it")
        extractor = get_extractor(config, get_settings())
    except ExtractionError as exc:
        _finish(db, job, "Failed", str(exc))
        return
    if services.cached_extraction(db, doc.file_sha256, extractor.provider, extractor.model):
        _finish(db, job, "Completed")
        return
    try:
        result = extractor.extract(read_pdf(doc.file_sha256), doc.file_name or "source.pdf")
    except ExtractionError as exc:
        if _still_running(db, job):
            _retry_or_fail(db, job, str(exc), exc.retryable)
        return
    if not _still_running(db, job):
        return
    services.save_extraction(db, doc.file_sha256, extractor.provider, extractor.model, result)
    _finish(db, job, "Completed")


def run_pending(db: Session, limit: int = 100) -> int:
    """Run queued jobs synchronously. Used by the worker loop and by tests."""
    done = 0
    recover_expired_leases(db)
    while done < limit:
        job = claim_next(db)
        if job is None:
            break
        run_job(db, job)
        done += 1
    return done


__all__ = ["ACTIVE", "claim_next", "recover_expired_leases", "run_job", "run_pending", "Extraction"]
