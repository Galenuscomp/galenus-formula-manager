from datetime import timedelta

import pytest

from app import crypto, jobs
from app.db import utcnow
from app.models import Job, SearchRequest, SourceAccount, SourceDocument
from app.search.automation import FoundDocument, SearchCooldown, SearchFailed
from tests.conftest import PDF


@pytest.fixture(autouse=True)
def ct_account(db, users):
    """The technician saved their CompoundingToday login, so their downloads are automated."""
    db.add(SourceAccount(user_id=users["tech"].id, source="CompoundingToday",
                         username_encrypted=crypto.encrypt("pharmacy"), password_encrypted=crypto.encrypt("secret")))
    db.commit()


def _create(api, sources=("CompoundingToday", "MEDISCA"), **extra):
    r = api.post("/api/requests", json={"active_ingredient": "Examplamide", "strength": "10 mg/mL",
                                        "dosage_form": "oral suspension", "sources": list(sources), **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _found(formula_id="CT-1", pdf=PDF):
    return FoundDocument(pdf=pdf, filename="f.pdf", source_name="CompoundingToday", source_formula_id=formula_id,
                         title="T", url="u")


def test_request_creation_queues_only_automated_sources_and_returns_immediately(client, db):
    req = _create(client("tech"))
    assert req["status"] == "Searching"
    job_rows = db.query(Job).filter_by(request_id=req["id"]).all()
    assert [j.source_name for j in job_rows] == ["CompoundingToday"]  # MEDISCA: manual upload, never a stuck job


def test_successful_search_stores_document(client, db, monkeypatch):
    api = client("tech")
    req = _create(api)
    monkeypatch.setattr(jobs, "fetch_source", lambda *a, **k: _found())
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

    monkeypatch.setattr(jobs, "fetch_source", limited)
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

    monkeypatch.setattr(jobs, "fetch_source", broken)
    jobs.run_pending(db)
    job = db.query(Job).filter_by(request_id=req["id"]).one()
    assert job.status == "Failed" and job.attempts == 1


def test_unexpected_crash_never_leaves_job_running(client, db, monkeypatch):
    req = _create(client("tech"))
    monkeypatch.setattr(jobs, "fetch_source", lambda *a, **k: 1 / 0)
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


def test_no_saved_login_means_no_automated_download(client, db):
    db.query(SourceAccount).delete()
    db.commit()
    api = client("tech")
    req = _create(api)
    assert db.query(Job).filter_by(request_id=req["id"]).count() == 0
    assert api.get("/api/config").json()["automated_sources"] == []
    r = api.post(f"/api/requests/{req['id']}/search", json={"source_name": "CompoundingToday"})
    assert r.status_code == 422 and "login" in r.json()["detail"]


def test_catalog_pick_downloads_that_exact_formula(client, db, monkeypatch):
    api = client("tech")
    ref = {"source": "CompoundingToday", "formula_id": "233", "title": "Baclofen 10-mg/mL",
           "url": "https://compoundingtoday.com/Formulation/FormulaInfo.cfm?ID=233"}
    req = _create(api, catalog_ref=ref)
    job = db.query(Job).filter_by(request_id=req["id"]).one()
    assert job.payload["formula_id"] == "233"
    seen = {}
    monkeypatch.setattr(jobs, "fetch_source", lambda db_, source, **k: seen.update(k) or _found("233"))
    jobs.run_pending(db)
    assert seen["formula_id"] == "233" and seen["title"] == "Baclofen 10-mg/mL"


def test_download_button_queues_one_formula(client, db, monkeypatch):
    api = client("tech")
    req = _create(api, sources=())
    body = {"source": "CompoundingToday", "formula_id": "11", "title": "X 1%", "url": ""}
    r = api.post(f"/api/requests/{req['id']}/download", json=body)
    assert r.status_code == 200 and r.json()["payload"]["formula_id"] == "11"
    assert api.post(f"/api/requests/{req['id']}/download", json=body).status_code == 409  # already running
    monkeypatch.setattr(jobs, "fetch_source", lambda *a, **k: _found("11"))
    jobs.run_pending(db)
    assert api.post(f"/api/requests/{req['id']}/download", json=body).status_code == 409  # already on the request
    # The same PDF downloaded again is not added twice.
    api.post(f"/api/requests/{req['id']}/download", json={**body, "formula_id": "12"})
    jobs.run_pending(db)
    assert db.query(SourceDocument).filter_by(request_id=req["id"]).count() == 1
    medisca = api.post(f"/api/requests/{req['id']}/download", json={**body, "source": "MEDISCA"})
    assert medisca.status_code == 422


def test_source_accounts_are_per_user_and_password_never_returned(client, db, users):
    pharm = client("pharm")
    r = pharm.put("/api/source-accounts/MEDISCA", json={"username": "lab@pharmacy.test"})
    assert r.status_code == 422  # a new account needs a password
    r = pharm.put("/api/source-accounts/MEDISCA", json={"username": "lab@pharmacy.test", "password": "Sup3r-secret"})
    assert r.status_code == 200 and "Sup3r-secret" not in r.text
    row = db.get(SourceAccount, (users["pharm"].id, "MEDISCA"))
    assert "Sup3r-secret" not in row.password_encrypted and crypto.decrypt(row.password_encrypted) == "Sup3r-secret"
    views = {v["source"]: v for v in pharm.get("/api/source-accounts").json()}
    assert views["MEDISCA"]["username"] == "lab@pharmacy.test" and views["CompoundingToday"]["configured"] is False
    # Each user sees only their own: the technician's CompoundingToday login, not the pharmacist's MEDISCA one.
    tech_views = {v["source"]: v for v in client("tech").get("/api/source-accounts").json()}
    assert tech_views["CompoundingToday"]["configured"] is True and tech_views["MEDISCA"]["configured"] is False
    assert client("pharm").get("/api/config").json()["automated_sources"] == ["MEDISCA"]
    # Changing only the username keeps the password.
    pharm.put("/api/source-accounts/MEDISCA", json={"username": "other@pharmacy.test"})
    db.refresh(row)
    assert crypto.decrypt(row.password_encrypted) == "Sup3r-secret"
    assert pharm.put("/api/source-accounts/Unknown", json={"username": "u", "password": "p"}).status_code == 404
    assert pharm.delete("/api/source-accounts/MEDISCA").json()[1]["configured"] is False


def test_source_account_login_check_result_is_kept(client, monkeypatch):
    from app.search import compounding_today

    tech = client("tech")
    seen = []
    monkeypatch.setattr(compounding_today, "check_login", lambda creds: seen.append(creds))
    r = tech.post("/api/source-accounts/CompoundingToday/test").json()
    assert r["ok"] is True and "successfully" in r["message"] and seen[0].key.startswith("compoundingtoday-")
    ct = {v["source"]: v for v in tech.get("/api/source-accounts").json()}["CompoundingToday"]
    assert ct["check_ok"] is True and ct["checked_at"]

    def rejected(creds):
        raise SearchFailed("CompoundingToday did not accept the username or password.", retryable=False)

    monkeypatch.setattr(compounding_today, "check_login", rejected)
    r = tech.post("/api/source-accounts/CompoundingToday/test").json()
    assert r["ok"] is False and "did not accept" in r["message"]
    ct = {v["source"]: v for v in r["accounts"]}["CompoundingToday"]
    assert ct["check_ok"] is False and "did not accept" in ct["check_message"]
    assert client("pharm").post("/api/source-accounts/CompoundingToday/test").status_code == 422  # none saved


def test_download_uses_the_requesting_users_login(client, db, users, monkeypatch):
    req = _create(client("tech"))
    job = db.query(Job).filter_by(request_id=req["id"]).one()
    assert job.requested_by == users["tech"].id
    seen = {}
    monkeypatch.setattr(jobs, "fetch_source", lambda db_, source, **k: seen.update(k) or _found())
    jobs.run_pending(db)
    assert seen["user_id"] == users["tech"].id
    # A pharmacist without a CompoundingToday login gets no automated download.
    assert db.query(Job).filter_by(request_id=_create(client("pharm"))["id"]).count() == 0


@pytest.fixture
def medisca_account(db, users):
    db.add(SourceAccount(user_id=users["tech"].id, source="MEDISCA",
                         username_encrypted=crypto.encrypt("lab@pharmacy.test"),
                         password_encrypted=crypto.encrypt("secret")))
    db.commit()


def test_medisca_search_or_exact_catalog_formula(client, db, monkeypatch, medisca_account):
    api = client("tech")
    # Without a catalog pick: a keyword search on MEDISCA's library.
    req = _create(api, sources=("MEDISCA",))
    job = db.query(Job).filter_by(request_id=req["id"]).one()
    assert job.source_name == "MEDISCA" and job.payload is None
    # From a catalog pick: that exact formula number.
    ref = {"source": "MEDISCA", "formula_id": "F000473", "title": "Diazepam 5 mg/mL Oral Liquid",
           "url": "https://www.medisca.com/formulas/library?q=F000473"}
    db.query(Job).delete()
    db.commit()
    req = _create(api, sources=("MEDISCA",), catalog_ref=ref)
    job = db.query(Job).filter_by(request_id=req["id"]).one()
    assert job.source_name == "MEDISCA" and job.payload["formula_id"] == "F000473"
    seen = {}
    monkeypatch.setattr(jobs, "fetch_source", lambda db_, source, **k: seen.update(source=source, **k) or FoundDocument(
        pdf=PDF, filename="m.pdf", source_name="MEDISCA", source_formula_id="F000473", title="Diazepam", url=ref["url"]))
    jobs.run_pending(db)
    assert seen["source"] == "MEDISCA" and seen["formula_id"] == "F000473" and seen["strength"] == "10 mg/mL"
    assert api.get(f"/api/requests/{req['id']}").json()["documents"][0]["source_formula_id"] == "F000473"


def test_medisca_search_picks_the_closest_formula():
    from app.search.medisca import best_match

    rows = [  # as MEDISCA's library lists them for "Diazepam"
        {"number": "F000474", "title": "Diazepam 5 mg/5 mL Oral Liquid (Suspension, 480 mL)", "route": "Oral", "form": "Liquid"},
        {"number": "F001603", "title": "Diazepam 25 mg/mL Rectal Gel", "route": "Rectal", "form": "Gel"},
        {"number": "F000452", "title": "Diazepam 5 mg Rectal Suppositories", "route": "Rectal", "form": "Suppository"},
        {"number": "F000473", "title": "Diazepam 5 mg per mL Oral Liquid (Suspension, 20 mL)", "route": "Oral", "form": "Liquid"},
    ]
    assert best_match(rows, "Diazepam", "5 mg/mL", "oral suspension")["number"] == "F000473"
    assert best_match(rows, "Diazepam", "5 mg", "suppository")["number"] == "F000452"
    assert best_match(rows, "Diazepam", "", "")["number"] == "F000474"  # nothing to go on: MEDISCA's first
    # A formula with another strength is never taken instead.
    assert best_match(rows, "Diazepam", "10 mg/mL", "oral suspension") is None
    combo = [{"number": "F1", "title": "Ketoprofen 10% Topical Cream", "route": "", "form": ""},
             {"number": "F3", "title": "Baclofen 2%, Ketoprofen 10%, Loperamide 5% Topical Gel", "route": "", "form": ""},
             {"number": "F4", "title": "Cyclobenzaprine 5%, Ketoprofen 10%, Lidocaine HCl 5% Topical Cream",
              "route": "", "form": ""},
             {"number": "F2", "title": "Ketoprofen 10%, Lidocaine Hydrochloride 5% Topical Cream", "route": "", "form": ""}]
    assert best_match(combo, "Ketoprofen, Lidocaine HCl", "10%, 5%", "cream")["number"] == "F2"
    assert best_match([], "X", "", "") is None


def test_medisca_adapter_rejects_malformed_numbers():
    from app.search import medisca
    from app.search.automation import Credentials

    with pytest.raises(SearchFailed) as info:
        medisca.fetch(Credentials("u", "p"), active_ingredient="Diazepam", formula_id="12; drop")
    assert info.value.retryable is False


def test_medisca_login_check(client, monkeypatch, medisca_account):
    from app.search import medisca

    monkeypatch.setattr(medisca, "check_login", lambda creds: None)
    assert client("tech").post("/api/source-accounts/MEDISCA/test").json()["ok"] is True
