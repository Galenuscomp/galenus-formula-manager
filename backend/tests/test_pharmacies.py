import io

from PIL import Image

from app.models import Decision
from app.pdf import _mirror_brackets, language
from tests.test_drafts import CONTENT, _decide, _draft, _save, _submit


def _png(color=(13, 148, 136)):
    buf = io.BytesIO()
    Image.new("RGB", (120, 60), color).save(buf, "PNG")
    return buf.getvalue()


def _pharmacy(api, name="Galenus Pharmacy", **extra):
    return api.post("/api/pharmacies", json={"name": name, "address": "1 Herzl St, Tel Aviv", **extra})


def _pending(client, db):
    tech = client("tech")
    _, _, draft = _draft(tech, db)
    _save(tech, draft["id"])
    assert _submit(tech, draft["id"]).status_code == 200
    return draft["id"]


def test_admin_limits_number_of_pharmacies(client, users):
    pharm = client("pharm")
    assert _pharmacy(pharm).status_code == 201
    r = _pharmacy(pharm, "Second branch")
    assert r.status_code == 422 and "up to 1" in r.json()["detail"]
    client("admin").patch(f"/api/users/{users['pharm'].id}", json={"max_pharmacies": 2})
    assert _pharmacy(pharm, "Second branch").status_code == 201
    listed = pharm.get("/api/pharmacies").json()
    assert listed["max"] == 2 and [p["name"] for p in listed["items"]] == ["Galenus Pharmacy", "Second branch"]
    assert _pharmacy(client("tech")).status_code == 403


def test_logo_upload_validates_images(client):
    pharm = client("pharm")
    pid = _pharmacy(pharm).json()["id"]
    upload = lambda data, name="logo.png": pharm.c.post(  # noqa: E731
        f"/api/pharmacies/{pid}/logo", headers={"X-Requested-With": "fm"}, files={"file": (name, data, "image/png")})
    assert upload(b"not an image").status_code == 422
    r = upload(_png())
    assert r.status_code == 200 and r.json()["has_logo"] is True
    assert pharm.get(f"/api/pharmacies/{pid}/logo").content.startswith(b"\x89PNG")
    # Someone else cannot change it.
    other = client("pharm2").c.post(f"/api/pharmacies/{pid}/logo", headers={"X-Requested-With": "fm"},
                                    files={"file": ("l.png", _png(), "image/png")})
    assert other.status_code == 404


def test_approval_records_the_issuing_pharmacy(client, db, users):
    draft_id = _pending(client, db)
    pharm = client("pharm")
    pid = _pharmacy(pharm, phone="03-1234567").json()["id"]
    pharm.c.post(f"/api/pharmacies/{pid}/logo", headers={"X-Requested-With": "fm"},
                 files={"file": ("l.png", _png(), "image/png")})
    r = _decide(pharm, draft_id)  # one pharmacy: used without asking
    assert r.status_code == 200, r.text
    assert r.json()["approval"]["pharmacy_name"] == "Galenus Pharmacy"
    decision = db.query(Decision).one()
    assert decision.pharmacy["address"] == "1 Herzl St, Tel Aviv" and decision.pharmacy["logo_sha256"]
    # Editing the pharmacy later does not change the approved record or its PDF.
    pharm.patch(f"/api/pharmacies/{pid}", json={"name": "Renamed"})
    db.refresh(decision)
    assert decision.pharmacy["name"] == "Galenus Pharmacy"
    assert pharm.get(f"/api/drafts/{draft_id}/pdf").content.startswith(b"%PDF-")


def test_several_pharmacies_require_a_choice(client, db, users):
    client("admin").patch(f"/api/users/{users['pharm'].id}", json={"max_pharmacies": 2})
    draft_id = _pending(client, db)
    pharm = client("pharm")
    _pharmacy(pharm, "Branch A")
    b = _pharmacy(pharm, "Branch B").json()["id"]
    other = _pharmacy(client("pharm2"), "Not mine").json()["id"]
    detail = pharm.get(f"/api/drafts/{draft_id}").json()
    body = {"decision": "approved", "notes": "", "content_sha256": detail["content_sha256"]}
    r = pharm.post(f"/api/drafts/{draft_id}/decision", json=body)
    assert r.status_code == 422 and "Choose which" in r.json()["detail"]
    assert pharm.post(f"/api/drafts/{draft_id}/decision", json={**body, "pharmacy_id": other}).status_code == 422
    r = pharm.post(f"/api/drafts/{draft_id}/decision", json={**body, "pharmacy_id": b})
    assert r.status_code == 200 and r.json()["approval"]["pharmacy_name"] == "Branch B"


def test_translate_returns_hebrew_without_saving(client, db):
    tech = client("tech")
    _, _, draft = _draft(tech, db)
    before = _save(tech, draft["id"])
    r = tech.post(f"/api/drafts/{draft['id']}/translate",
                  json={"fields": {"preparation_method": "1. Weigh\n2. Mix", "warnings": "", "strength": "10 mg/mL"}})
    assert r.status_code == 200, r.text
    assert r.json()["translations"] == {"preparation_method": "[עברית] 1. Weigh\n2. Mix"}  # names/strengths untouched
    assert tech.get(f"/api/drafts/{draft['id']}").json()["row_version"] == before["row_version"]
    assert tech.post(f"/api/drafts/{draft['id']}/translate", json={"fields": {"strength": "1"}}).status_code == 422


def test_reviewer_cannot_translate_a_pending_draft(client, db):
    draft_id = _pending(client, db)
    r = client("pharm").post(f"/api/drafts/{draft_id}/translate", json={"fields": {"warnings": "None"}})
    assert r.status_code == 409


def test_hebrew_pdf(client, db):
    tech = client("tech")
    _, _, draft = _draft(tech, db)
    hebrew = {**CONTENT, "preparation_method": "1. לשקול 2 g של Baclofen USP (levigate).\n2. להשלים ל-200 mL",
              "warnings": "אין"}
    _save(tech, draft["id"], hebrew)
    assert language(hebrew) == "he" and language(CONTENT) == "en"
    assert tech.get(f"/api/drafts/{draft['id']}/pdf").content.startswith(b"%PDF-")


def test_brackets_face_the_right_way_in_hebrew():
    # English inside brackets after Hebrew: the pair belongs to the right-to-left text.
    assert _mirror_brackets("תאריך שימוש אחרון (BUD): 30") == "תאריך שימוש אחרון )BUD(: 30"
    assert _mirror_brackets("במרגמה (triturate).") == "במרגמה )triturate(."
    # Inside English text, or an English line with a Hebrew note, brackets stay as they are.
    assert _mirror_brackets("Ora-Plus (sterile) water", "L") == "Ora-Plus (sterile) water"
    assert _mirror_brackets("Baclofen USP — 1 g (חומר פעיל)", "L") == "Baclofen USP — 1 g (חומר פעיל)"
    # English brackets inside a Hebrew line are kept with their English text by a direction mark.
    assert _mirror_brackets("בקירור (USP <795>).") == "בקירור )USP <795>‎(."
