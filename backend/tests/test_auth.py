from tests.conftest import PASSWORD


def test_login_rejects_wrong_password(client):
    api = client()
    r = api.post("/api/auth/login", json={"email": "tech@example.test", "password": "wrong-password"})
    assert r.status_code == 401


def test_me_requires_session(client):
    assert client().get("/api/auth/me").status_code == 401
    me = client("tech").get("/api/auth/me").json()
    assert me["role"] == "technician"
    assert "password_hash" not in me


def test_mutations_require_custom_header(client):
    api = client("tech")
    r = api.c.post("/api/requests", json={"active_ingredient": "X"})  # no X-Requested-With
    assert r.status_code == 403


def test_cross_origin_rejected(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "public_origin", "https://formulas.example.test")
    api = client("tech")
    r = api.c.post("/api/requests", json={"active_ingredient": "X"},
                   headers={"X-Requested-With": "fm", "Origin": "https://evil.test"})
    assert r.status_code == 403


def test_logout_revokes_session(client):
    api = client("tech")
    assert api.post("/api/auth/logout").status_code == 200
    assert api.get("/api/auth/me").status_code == 401


def test_only_admin_manages_users(client):
    assert client("pharm").get("/api/users").status_code == 403
    admin = client("admin")
    r = admin.post("/api/users", json={"email": "New@Example.test", "full_name": "New", "role": "pharmacist",
                                       "licence_number": "PH-9", "password": PASSWORD})
    assert r.status_code == 201
    assert r.json()["email"] == "new@example.test"
    assert admin.post("/api/users", json={"email": "new@example.test", "full_name": "Dup", "role": "technician",
                                          "password": PASSWORD}).status_code == 409


def test_disabling_user_ends_their_sessions(client, users):
    tech = client("tech")
    admin = client("admin")
    assert admin.patch(f"/api/users/{users['tech'].id}", json={"is_active": False}).status_code == 200
    assert tech.get("/api/auth/me").status_code == 401


def test_admin_cannot_prepare_or_approve(client):
    assert client("admin").post("/api/requests", json={"active_ingredient": "X"}).status_code == 403
