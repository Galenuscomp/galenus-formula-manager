import pytest

from app import jobs
from app.ai.base import ExtractionError, ExtractionResult
from app.ai.fake import FakeExtractor
from app.ai.openai_provider import OpenAIExtractor
from app.models import Extraction, Job, UserAISettings
from tests.conftest import PDF

KEY = "sk-test-0123456789abcd"


@pytest.fixture
def openai_ok(monkeypatch):
    """OpenAI accepts any key and model; extraction returns the fake output."""
    monkeypatch.setattr(OpenAIExtractor, "verify", lambda self: None)
    seen = []

    def extract(self, pdf, filename):
        seen.append(self.client.api_key)
        return ExtractionResult(output=FakeExtractor().extract(pdf, filename).output, model=self.model)

    monkeypatch.setattr(OpenAIExtractor, "extract", extract)
    return seen


def _draft(api):
    req = api.post("/api/requests", json={"active_ingredient": "Examplamide", "sources": []}).json()
    doc = api.post(f"/api/requests/{req['id']}/documents", data={"source_name": "MEDISCA"},
                   files={"file": ("m.pdf", PDF, "application/pdf")}).json()
    return api.post(f"/api/requests/{req['id']}/drafts", json={"source_document_ids": [doc["id"]]}).json()


def test_default_follows_server(client):
    api = client("tech")
    view = api.get("/api/account/ai").json()
    assert view["provider"] == "default" and view["server_default"]["provider"] == "fake"
    assert api.get("/api/config").json()["ai_enabled"] is True


def test_save_openai_key_is_encrypted_and_never_returned(client, db, openai_ok):
    api = client("tech")
    r = api.put("/api/account/ai", json={"provider": "openai", "model": "gpt-6.1-sol", "api_key": KEY})
    assert r.status_code == 200, r.text
    assert KEY not in r.text and r.json()["key_last4"] == "abcd"
    row = db.query(UserAISettings).one()
    assert row.api_key_encrypted and KEY not in row.api_key_encrypted
    assert KEY not in api.get("/api/account/ai").text
    # Changing only the model keeps the saved key.
    r = api.put("/api/account/ai", json={"provider": "openai", "model": "gpt-6-luna"})
    assert r.status_code == 200 and r.json()["model"] == "gpt-6-luna" and r.json()["key_last4"] == "abcd"
    assert api.post("/api/account/ai/test").json()["provider"] == "openai"


def test_new_provider_requires_its_own_key(client, openai_ok):
    api = client("tech")
    api.put("/api/account/ai", json={"provider": "openai", "model": "gpt-6.1-sol", "api_key": KEY})
    r = api.put("/api/account/ai", json={"provider": "anthropic", "model": "claude-opus-5"})
    assert r.status_code == 422 and "API key" in r.json()["detail"]
    assert api.put("/api/account/ai", json={"provider": "openai", "api_key": KEY}).status_code == 422


def test_rejected_key_is_not_saved(client, db, monkeypatch):
    def reject(self):
        raise ExtractionError("OpenAI rejected the API key")

    monkeypatch.setattr(OpenAIExtractor, "verify", reject)
    r = client("tech").put("/api/account/ai", json={"provider": "openai", "model": "m", "api_key": KEY})
    assert r.status_code == 422 and r.json()["detail"] == "OpenAI rejected the API key"
    assert db.query(UserAISettings).count() == 0


def test_extraction_uses_requesting_users_key(client, db, openai_ok):
    tech = client("tech")
    tech.put("/api/account/ai", json={"provider": "openai", "model": "gpt-6.1-sol", "api_key": KEY})
    draft = _draft(tech)
    job = db.query(Job).filter_by(kind="extract").one()
    assert job.requested_by is not None
    jobs.run_pending(db)
    assert openai_ok == [KEY]
    ext = db.query(Extraction).one()
    assert (ext.provider, ext.model) == ("openai", "gpt-6.1-sol")
    # A user on the server default sees the same result on the shared draft.
    assert client("pharm").get(f"/api/drafts/{draft['id']}").json()["extractions"]


def test_none_turns_extraction_off(client, db):
    tech = client("tech")
    assert tech.put("/api/account/ai", json={"provider": "none"}).status_code == 200
    assert tech.get("/api/config").json()["ai_enabled"] is False
    draft = _draft(tech)
    assert db.query(Job).filter_by(kind="extract").count() == 0
    r = tech.post(f"/api/drafts/{draft['id']}/extract")
    assert r.status_code == 422 and "turned off" in r.json()["detail"]
    # Back to the server default.
    tech.put("/api/account/ai", json={"provider": "default"})
    assert db.query(UserAISettings).count() == 0
    assert tech.post(f"/api/drafts/{draft['id']}/extract").json()["queued"] == 1


def test_admin_sees_provider_not_key(client, openai_ok):
    client("tech").put("/api/account/ai", json={"provider": "openai", "model": "gpt-6.1-sol", "api_key": KEY})
    r = client("admin").get("/api/users")
    by_email = {u["email"]: u for u in r.json()}
    assert by_email["tech@example.test"]["ai_provider"] == "openai"
    assert by_email["pharm@example.test"]["ai_provider"] == "default"
    assert KEY not in r.text and "key_last4" not in r.text


def test_missing_secrets_key_refuses_to_store(client, settings, monkeypatch, openai_ok):
    monkeypatch.setattr(settings, "secrets_key", None)
    r = client("tech").put("/api/account/ai", json={"provider": "openai", "model": "m", "api_key": KEY})
    assert r.status_code == 422 and "SECRETS_KEY" in r.json()["detail"]
