import json
from types import SimpleNamespace

import pytest

from app.ai.anthropic_provider import AnthropicExtractor
from app.ai.base import ExtractionError
from app.ai.openai_provider import OpenAIExtractor
from app.ai.schema import strict_schema

PDF = b"%PDF-1.4 test"


def _walk(node):
    yield node
    for child in (node.get("properties") or {}).values():
        yield from _walk(child)
    if isinstance(node.get("items"), dict):
        yield from _walk(node["items"])


def test_strict_schema_closes_every_object():
    for node in _walk(strict_schema()):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])


def _anthropic_response(stop_reason="end_turn", text='{"formula_title": "X"}'):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        model="claude-opus-5",
    )


def test_anthropic_request_shape(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    ex = AnthropicExtractor("claude-opus-5")
    captured = {}

    def create(**kw):
        captured.update(kw)
        return _anthropic_response()

    monkeypatch.setattr(ex.client.beta.messages, "create", create)
    result = ex.extract(PDF, "f.pdf")
    assert result.output == {"formula_title": "X"}
    assert captured["model"] == "claude-opus-5"
    assert captured["fallbacks"] == "default"
    assert captured["output_config"]["format"]["type"] == "json_schema"
    doc = captured["messages"][0]["content"][0]
    assert doc["type"] == "document" and doc["source"]["media_type"] == "application/pdf"


def test_anthropic_refusal_and_truncation(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    ex = AnthropicExtractor("claude-opus-5", fallbacks="off")
    for reason in ("refusal", "max_tokens"):
        monkeypatch.setattr(ex.client.messages, "create", lambda **kw: _anthropic_response(stop_reason=reason))
        with pytest.raises(ExtractionError):
            ex.extract(PDF, "f.pdf")


def test_openai_request_shape(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    ex = OpenAIExtractor("some-model")
    captured = {}

    def create(**kw):
        captured.update(kw)
        return SimpleNamespace(status="completed", output_text=json.dumps({"formula_title": "Y"}),
                               usage=None, model="some-model")

    monkeypatch.setattr(ex.client.responses, "create", create)
    assert ex.extract(PDF, "f.pdf").output == {"formula_title": "Y"}
    fmt = captured["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True
    assert captured["input"][0]["content"][0]["file_data"].startswith("data:application/pdf;base64,")
