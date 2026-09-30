import pytest

from app import mail
from app.models import PasswordToken
from tests.test_drafts import _decide, _draft, _save, _submit


@pytest.fixture
def outbox(settings, monkeypatch):
    """E-mail is set up; messages are captured instead of sent."""
    monkeypatch.setattr(settings, "resend_api_key", "re_test")
    monkeypatch.setattr(settings, "public_origin", "https://formulas.example.test")
    sent = []
    monkeypatch.setattr(mail, "send", lambda m: sent.append(m))
    return sent


def test_new_user_gets_invitation_email(client, outbox):
    r = client("admin").post("/api/users", json={"email": "new@example.test", "full_name": "New User",
                                                  "role": "technician"})
    assert r.json()["password_link"]["emailed"] is True
    [m] = outbox
    token = r.json()["password_link"]["path"].split("=", 1)[1]
    assert m.to == "new@example.test" and token in m.html and token in m.text
    assert "https://formulas.example.test/set-password#token=" in m.html


def test_reset_link_is_emailed_and_use_sends_alert(client, users, outbox):
    link = client("admin").post(f"/api/users/{users['tech'].id}/password-link").json()
    assert link["emailed"] is True and outbox[-1].subject == "איפוס סיסמה"
    token = link["path"].split("=", 1)[1]
    client().post("/api/auth/password-link", json={"token": token, "new_password": "Fresh password 42"})
    assert outbox[-1].to == "tech@example.test" and outbox[-1].subject == "הסיסמה שלך שונתה"


def test_forgot_password_is_self_service_and_quiet(client, db, users, outbox):
    anon = client()
    assert anon.post("/api/auth/forgot-password", json={"email": "Tech@Example.test"}).json()["email_enabled"] is True
    assert len(outbox) == 1 and outbox[0].to == "tech@example.test"
    # Same answer for unknown addresses, and no second link within 5 minutes.
    assert anon.post("/api/auth/forgot-password", json={"email": "nobody@example.test"}).status_code == 200
    anon.post("/api/auth/forgot-password", json={"email": "tech@example.test"})
    assert len(outbox) == 1 and db.query(PasswordToken).count() == 1


def test_forgot_password_without_email_setup(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", None)
    assert client().post("/api/auth/forgot-password", json={"email": "tech@example.test"}).json() == {
        "ok": True, "email_enabled": False}


def test_approval_emails(client, db, outbox):
    tech = client("tech")
    _, _, draft = _draft(tech, db)
    _save(tech, draft["id"])
    _submit(tech, draft["id"])
    # Both pharmacists are asked; the submitter (a technician) is not.
    assert sorted(m.to for m in outbox) == ["pharm2@example.test", "pharm@example.test"]
    assert f"/drafts/{draft['id']}" in outbox[0].html
    outbox.clear()
    _decide(client("pharm"), draft["id"], "returned", notes="Check the BUD <source>")
    [m] = outbox
    assert m.to == "tech@example.test" and "הוחזרה לתיקון" in m.subject
    assert "Check the BUD &lt;source&gt;" in m.html  # user text is escaped


def test_changing_own_password_sends_alert(client, outbox):
    client("tech").post("/api/auth/password", json={"current_password": "correct horse battery 7",
                                                     "new_password": "Fresh password 42"})
    assert outbox[-1].subject == "הסיסמה שלך שונתה"


def test_admin_test_email(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", None)
    admin = client("admin")
    assert admin.get("/api/users/mail").json()["enabled"] is False
    r = admin.post("/api/users/mail/test")
    assert r.status_code == 422 and "RESEND_API_KEY" in r.json()["detail"]
    monkeypatch.setattr(settings, "resend_api_key", "re_test")
    monkeypatch.setattr(mail, "send", lambda m: None)
    assert admin.post("/api/users/mail/test").json() == {"ok": True, "to": "admin@example.test"}
    assert client("tech").post("/api/users/mail/test").status_code == 403


def test_nothing_is_sent_without_setup(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", None)
    calls = []
    monkeypatch.setattr(mail.httpx, "post", lambda *a, **k: calls.append(a))
    r = client("admin").post("/api/users", json={"email": "x@example.test", "full_name": "X", "role": "technician"})
    assert r.json()["password_link"]["emailed"] is False and calls == []
