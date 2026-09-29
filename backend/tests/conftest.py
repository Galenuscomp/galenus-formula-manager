import os

import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app.config import get_settings
from app.db import Base
from app.models import User
from app.security import hash_password

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PASSWORD = "correct horse battery 7"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    # TEST_DATABASE_URL runs the same suite against a disposable PostgreSQL database.
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path}/test.db"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    monkeypatch.setenv("SECRETS_KEY", "test-secrets-key")
    monkeypatch.setenv("FORMULA_AUTOMATION_URL", "http://automation.test/pdf")
    monkeypatch.setenv("FORMULA_AUTOMATION_API_KEY", "test-key")
    get_settings.cache_clear()
    engine = dbmod.configure(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield get_settings()
    engine.dispose()
    get_settings.cache_clear()


@pytest.fixture
def db(settings):
    with dbmod.session_factory()() as session:
        yield session


@pytest.fixture
def users(db):
    made = {}
    for key, role, licence in [
        ("admin", "admin", None),
        ("tech", "technician", None),
        ("pharm", "pharmacist", "PH-1001"),
        ("pharm2", "pharmacist", "PH-1002"),
    ]:
        u = User(email=f"{key}@example.test", full_name=f"{key.title()} User", role=role,
                 licence_number=licence, password_hash=hash_password(PASSWORD))
        db.add(u)
        made[key] = u
    db.commit()
    return made


class Api:
    def __init__(self, client: TestClient):
        self.c = client

    def _h(self):
        return {"X-Requested-With": "fm"}

    def login(self, who: str):
        r = self.c.post("/api/auth/login", json={"email": f"{who}@example.test", "password": PASSWORD},
                        headers=self._h())
        assert r.status_code == 200, r.text
        return self

    def get(self, url, **kw):
        return self.c.get(url, headers=self._h(), **kw)

    def post(self, url, **kw):
        return self.c.post(url, headers=self._h(), **kw)

    def put(self, url, **kw):
        return self.c.put(url, headers=self._h(), **kw)

    def patch(self, url, **kw):
        return self.c.patch(url, headers=self._h(), **kw)


@pytest.fixture
def client(settings, users):
    from app.main import app

    def make(who: str | None = None) -> Api:
        api = Api(TestClient(app))
        return api.login(who) if who else api

    return make
