from app import jobs
from app.models import Extraction, Job
from tests.conftest import PDF

CONTENT = {
    "active_ingredient": "Examplamide Hydrochloride",
    "proposed_formula_name": "Examplamide 10 mg/mL Oral Suspension",
    "strength": "10 mg/mL",
    "dosage_form": "oral suspension",
    "final_quantity": "200 mL",
    "ingredients": "Examplamide HCl (active) — 2 g",
    "preparation_method": "1. Weigh\n2. Mix",
    "equipment": "Balance",
    "packaging": "Amber bottle",
    "storage_conditions": "Refrigerate",
    "bud": "14 days",
    "labelling_instructions": "Shake well",
    "warnings": "None stated",
    "references": "Fictional",
    "active_ingredients": [{"ingredient_name": "Examplamide", "salt_form": "Hydrochloride",
                            "strength_value": "10", "strength_unit": "mg/mL",
                            "quantity_value": "2", "quantity_unit": "g"}],
}


def _draft(api, db):
    req = api.post("/api/requests", json={"active_ingredient": "Examplamide", "sources": []}).json()
    doc = api.post(f"/api/requests/{req['id']}/documents", data={"source_name": "MEDISCA"},
                   files={"file": ("m.pdf", PDF, "application/pdf")}).json()
    d = api.post(f"/api/requests/{req['id']}/drafts", json={"source_document_ids": [doc["id"]]})
    assert d.status_code == 201, d.text
    return req, doc, d.json()


def _save(api, draft_id, content=CONTENT):
    detail = api.get(f"/api/drafts/{draft_id}").json()
    r = api.put(f"/api/drafts/{draft_id}", json={"content": content, "row_version": detail["row_version"]})
    assert r.status_code == 200, r.text
    return r.json()


def _submit(api, draft_id):
    detail = api.get(f"/api/drafts/{draft_id}").json()
    return api.post(f"/api/drafts/{draft_id}/submit", json={"row_version": detail["row_version"]})


def _decide(api, draft_id, decision="approved", notes="", sha=None):
    detail = api.get(f"/api/drafts/{draft_id}").json()
    return api.post(f"/api/drafts/{draft_id}/decision",
                    json={"decision": decision, "notes": notes, "content_sha256": sha or detail["content_sha256"]})


def test_extraction_runs_in_background_and_is_cached(client, db):
    api = client("tech")
    req, doc, draft = _draft(api, db)
    assert db.query(Job).filter_by(kind="extract").count() == 1
    jobs.run_pending(db)
    detail = api.get(f"/api/drafts/{draft['id']}").json()
    assert detail["extractions"][doc["id"]]["output"]["formula_title"].startswith("Fictional")
    assert detail["extraction_jobs"][0]["status"] == "Completed"
    # Same file in a second draft reuses the cached extraction: no new job, no new AI call.
    api.post(f"/api/requests/{req['id']}/drafts", json={"source_document_ids": [doc["id"]]})
    assert db.query(Job).filter_by(kind="extract").count() == 1
    assert db.query(Extraction).count() == 1


def test_full_review_flow(client, db):
    tech, pharm = client("tech"), client("pharm")
    req, doc, draft = _draft(tech, db)
    did = draft["id"]
    assert _submit(tech, did).status_code == 422  # mandatory fields missing
    _save(tech, did)
    assert _submit(tech, did).status_code == 200
    assert _decide(tech, did).status_code == 403  # technicians cannot decide
    assert _decide(pharm, did, sha="0" * 64).status_code == 409  # stale view
    r = _decide(pharm, did)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "Approved"
    approval = body["approval"]
    assert approval["actor_licence"] == "PH-1001" and approval["preparer_name"] == "Tech User"
    assert len(approval["pdf_sha256"]) == 64
    pdf = pharm.get(f"/api/drafts/{did}/pdf")
    assert pdf.content.startswith(b"%PDF-")
    assert tech.get(f"/api/requests/{req['id']}").json()["status"] == "Approved"
    # Approved content is locked.
    assert tech.put(f"/api/drafts/{did}", json={"content": CONTENT, "row_version": body["row_version"]}).status_code == 409
    # A revision is a new draft; the approved one stays as it was.
    rev = tech.post(f"/api/drafts/{did}/revise").json()
    assert rev["version"] == 2 and rev["predecessor_id"] == did
    assert tech.post(f"/api/drafts/{did}/revise").status_code == 409
    assert pharm.get(f"/api/drafts/{did}").json()["status"] == "Approved"
    lib = tech.get("/api/library").json()["items"]
    assert [i["id"] for i in lib] == [did] and lib[0]["superseded"] is False


def test_submitter_cannot_approve_own_draft(client, db):
    pharm, pharm2 = client("pharm"), client("pharm2")
    _, _, draft = _draft(pharm, db)
    _save(pharm, draft["id"])
    assert _submit(pharm, draft["id"]).status_code == 200
    assert _decide(pharm, draft["id"]).status_code == 403
    assert _decide(pharm2, draft["id"]).status_code == 200


def test_editing_pending_draft_requires_resubmission(client, db):
    tech, pharm = client("tech"), client("pharm")
    _, _, draft = _draft(tech, db)
    _save(tech, draft["id"])
    _submit(tech, draft["id"])
    seen = pharm.get(f"/api/drafts/{draft['id']}").json()["content_sha256"]
    after = _save(tech, draft["id"], {**CONTENT, "warnings": "Changed"})
    assert after["status"] == "Draft created"
    assert _decide(pharm, draft["id"], sha=seen).status_code == 409


def test_reviewer_cannot_edit_a_pending_draft(client, db):
    tech, pharm = client("tech"), client("pharm")
    _, _, draft = _draft(tech, db)
    _save(tech, draft["id"])
    _submit(tech, draft["id"])
    detail = pharm.get(f"/api/drafts/{draft['id']}").json()
    assert detail["permissions"]["can_edit"] is False and detail["permissions"]["can_decide"] is True
    r = pharm.put(f"/api/drafts/{draft['id']}", json={"content": {**CONTENT, "warnings": "Changed"},
                                                      "row_version": detail["row_version"]})
    assert r.status_code == 409 and "waiting for approval" in r.json()["detail"]
    # Still pending, still submitted by the technician, so the pharmacist can decide.
    assert _decide(pharm, draft["id"]).status_code == 200


def test_concurrent_edit_conflict(client, db):
    tech = client("tech")
    _, _, draft = _draft(tech, db)
    rv = tech.get(f"/api/drafts/{draft['id']}").json()["row_version"]
    assert tech.put(f"/api/drafts/{draft['id']}", json={"content": CONTENT, "row_version": rv}).status_code == 200
    assert tech.put(f"/api/drafts/{draft['id']}", json={"content": CONTENT, "row_version": rv}).status_code == 409


def test_reject_and_return_require_notes(client, db):
    tech, pharm = client("tech"), client("pharm")
    _, _, draft = _draft(tech, db)
    _save(tech, draft["id"])
    _submit(tech, draft["id"])
    assert _decide(pharm, draft["id"], "returned").status_code == 422
    r = _decide(pharm, draft["id"], "returned", notes="Check BUD source")
    assert r.json()["status"] == "Requires correction"
    assert r.json()["decisions"][0]["notes"] == "Check BUD source"
    assert _submit(tech, draft["id"]).status_code == 200


def test_active_ingredient_rules(client, db):
    tech = client("tech")
    _, _, draft = _draft(tech, db)
    bad = {**CONTENT, "active_ingredients": [
        {"ingredient_name": "A", "strength_value": "", "quantity_value": "1"},
        {"ingredient_name": "B", "included_in_local_formula": False},
    ]}
    _save(tech, draft["id"], bad)
    r = _submit(tech, draft["id"])
    assert r.status_code == 422
    errors = " ".join(r.json()["errors"])
    assert '"A" requires a strength value' in errors and '"B" requires an exclusion reason' in errors


def test_unknown_content_fields_rejected(client, db):
    tech = client("tech")
    _, _, draft = _draft(tech, db)
    r = tech.put(f"/api/drafts/{draft['id']}", json={"content": {"status": "Approved"}, "row_version": 1})
    assert r.status_code == 422


def test_preview_pdf_for_unapproved_draft(client, db):
    tech = client("tech")
    _, _, draft = _draft(tech, db)
    _save(tech, draft["id"], {**CONTENT, "local_adaptation_notes": "הערה בעברית"})
    assert tech.get(f"/api/drafts/{draft['id']}/pdf").content.startswith(b"%PDF-")
