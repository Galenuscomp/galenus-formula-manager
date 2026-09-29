from datetime import timedelta

import pytest

from app.db import utcnow
from app.models import AuditEvent, PasswordToken
from app.security import password_problems
from tests.conftest import PASSWORD

NEW = "Fresh password 42"


def _token(link):
    assert link["path"].startswith("/set-password#token=")
    return link["path"].split("=", 1)[1]


@pytest.mark.parametrize("password, problem", [
    ("short1", "at least 10"),
    ("no digits in here", "digit"),
    ("1234567890", "letter"),
    ("newuser2026x", "e-mail"),
])
def test_password_rules(password, problem):
    assert any(problem in p for p in password_problems(password, "newuser@example.test"))


def test_good_password_passes():
    assert password_problems(NEW, "someone@example.test") == []


def test_invite_flow(client):
    admin = client("admin")
    r = admin.post("/api/users", json={"email": "new@example.test", "full_name": "New User", "role": "technician"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["has_password"] is False and body["password_link"]["purpose"] == "invite"
    token = _token(body["password_link"])
    # Cannot sign in before choosing a password.
    anon = client()
    assert anon.post("/api/auth/login", json={"email": "new@example.test", "password": "!"}).status_code == 401
    info = anon.post("/api/auth/password-link/check", json={"token": token}).json()
    assert info == {"email": "new@example.test", "full_name": "New User", "purpose": "invite"}
    weak = anon.post("/api/auth/password-link", json={"token": token, "new_password": "weak"})
    assert weak.status_code == 422 and len(weak.json()["errors"]) >= 2
    assert anon.post("/api/auth/password-link", json={"token": token, "new_password": NEW}).status_code == 200
    assert anon.post("/api/auth/login", json={"email": "new@example.test", "password": NEW}).status_code == 200
    # One-time only.
    assert anon.post("/api/auth/password-link", json={"token": token, "new_password": NEW}).status_code == 410
    listed = {u["email"]: u for u in admin.get("/api/users").json()}
    assert listed["new@example.test"]["has_password"] is True


def test_reset_link_replaces_password_and_ends_sessions(client, users, db):
    tech, admin = client("tech"), client("admin")
    first = admin.post(f"/api/users/{users['tech'].id}/password-link").json()
    link = admin.post(f"/api/users/{users['tech'].id}/password-link").json()
    assert link["purpose"] == "reset"
    anon = client()
    # A newer link replaces the earlier one.
    assert anon.post("/api/auth/password-link/check", json={"token": _token(first)}).status_code == 410
    assert anon.post("/api/auth/password-link", json={"token": _token(link), "new_password": NEW}).status_code == 200
    assert tech.get("/api/auth/me").status_code == 401
    assert anon.post("/api/auth/login", json={"email": "tech@example.test", "password": PASSWORD}).status_code == 401
    assert anon.post("/api/auth/login", json={"email": "tech@example.test", "password": NEW}).status_code == 200
    assert db.query(AuditEvent).filter_by(action="password_set_by_reset_link").count() == 1


def test_expired_and_unknown_links(client, users, db):
    link = client("admin").post(f"/api/users/{users['tech'].id}/password-link").json()
    db.query(PasswordToken).update({"expires_at": utcnow() - timedelta(minutes=1)})
    db.commit()
    anon = client()
    assert anon.post("/api/auth/password-link/check", json={"token": _token(link)}).status_code == 410
    assert anon.post("/api/auth/password-link/check", json={"token": "x" * 43}).status_code == 410


def test_only_admin_creates_links(client, users):
    assert client("pharm").post(f"/api/users/{users['tech'].id}/password-link").status_code == 403


def test_change_password_applies_rules(client):
    api = client("tech")
    r = api.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "onlyletters"})
    assert r.status_code == 422 and "digit" in r.json()["detail"]
    assert api.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": NEW}).status_code == 200


def test_admin_created_password_must_follow_rules(client):
    r = client("admin").post("/api/users", json={"email": "p@example.test", "full_name": "P", "role": "technician",
                                                 "password": "tooweak"})
    assert r.status_code == 422
