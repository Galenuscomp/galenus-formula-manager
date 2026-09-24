from datetime import timedelta

from app import jobs
from app.db import utcnow
from app.models import Job, SearchRequest
from app.search.automation import FoundDocument, SearchCooldown, SearchFailed
from tests.conftest import PDF


def _create(api, sources=("CompoundingToday", "MEDISCA")):
    r = api.post("/api/requests", json={"active_ingredient": "Examplamide", "strength": "10 mg/mL",
                                        "dosage_form": "oral suspension", "sources": list(sources)})
    assert r.status_code == 201, r.text
    return r.json()


def test_request_creation_queues_only_automated_sources_and_returns_immediately(client, db):
    req = _create(client("tech"))
    assert req["status"] == "Searching"
    job_rows = db.query(Job).filter_by(request_id=req["id"]).all()
    assert [j.source_name for j in job_rows] == ["CompoundingToday"]  # MEDISCA: manual upload, never a stuck job


def test_successful_search_stores_document(client, db, monkeypatch):
    api = client("tech")
    req = _create(api)
    monkeypatch.setattr(jobs, "fetch_compounding_today", lambda *a, **k: FoundDocument(
        pdf=PDF, filename="f.pdf", source_name="CompoundingToday", source_formula_id="CT-1", title="T", url="u"))
    assert jobs.run_pending(db) == 1
    detail = api.get(f"/api/requests/{req['id']}").json()
    assert detail["status"] == "Formula found"
    assert detail["jobs"][0]["status"] == "Completed"
    assert detail["documents"][0]["source_formula_id"] == "CT-1"
    assert len(detail["documents"][0]["file_sha256"]) == 64


def test_rate_limit_requeues_then_ends_in_cooldown(client, db, monkeypatch):
    req = _create(client("tech"))

    def limited(*a, **k):
        raise SearchCooldown()

    monkeypatch.setattr(jobs, "fetch_compounding_today", limited)
    jobs.run_pending(db)
    job = db.query(Job).filter_by(request_id=req["id"]).one()
    assert job.status == "Queued" and job.run_after > utcnow()
    for _ in range(5):
        job.run_after = utcnow() - timedelta(seconds=1)
        db.commit()
        jobs.run_pending(db)
        db.refresh(job)
    assert job.status == "Cooldown"
    assert db.get(SearchRequest, req["id"]).status == "Error"


def test_non_retryable_failure_fails_fast(client, db, monkeypatch):
    req = _create(client("tech"))

    def broken(*a, **k):
        raise SearchFailed("Search worker returned 400", retryable=False)

    monkeypatch.setattr(jobs, "fetch_compounding_today", broken)
    jobs.run_pending(db)
    job = db.query(Job).filter_by(request_id=req["id"]).one()
    assert job.status == "Failed" and job.attempts == 1


def test_unexpected_crash_never_leaves_job_running(client, db, monkeypatch):
    req = _create(client("tech"))
    monkeypatch.setattr(jobs, "fetch_compounding_today", lambda *a, **k: 1 / 0)
    jobs.run_pending(db)
    job = db.query(Job).filter_by(request_id=req["id"]).one()
    assert job.status == "Failed"


def test_expired_lease_is_recovered(client, db):
    req = _create(client("tech"))
    job = db.query(Job).filter_by(request_id=req["id"]).one()
    job.status, job.attempts = "Running", 1
    job.lease_expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert jobs.recover_expired_leases(db) == 1
    db.refresh(job)
    assert job.status == "Queued"


def test_job_claimed_only_once(client, db):
    _create(client("tech"))
    first = jobs.claim_next(db)
    assert first is not None
    assert jobs.claim_next(db) is None


def test_cancel_and_retry(client, db):
    api = client("tech")
    req = _create(api)
    job = db.query(Job).filter_by(request_id=req["id"]).one()
    assert api.post(f"/api/requests/{req['id']}/search", json={"source_name": "CompoundingToday"}).status_code == 409
    assert api.post(f"/api/jobs/{job.id}/cancel").json()["status"] == "Cancelled"
    assert api.get(f"/api/requests/{req['id']}").json()["status"] == "No formula found"
    assert api.post(f"/api/requests/{req['id']}/search", json={"source_name": "CompoundingToday"}).status_code == 200
    assert api.post(f"/api/requests/{req['id']}/search", json={"source_name": "MEDISCA"}).status_code == 422


def test_upload_rejects_non_pdf(client):
    api = client("tech")
    req = _create(api, sources=())
    r = api.post(f"/api/requests/{req['id']}/documents", data={"source_name": "MEDISCA"},
                 files={"file": ("x.pdf", b"<html>not a pdf</html>", "application/pdf")})
    assert r.status_code == 400
    r = api.post(f"/api/requests/{req['id']}/documents", data={"source_name": "MEDISCA"},
                 files={"file": ("x.pdf", PDF, "application/pdf")})
    assert r.status_code == 201
    assert api.get(f"/api/documents/{r.json()['id']}/file").content == PDF
