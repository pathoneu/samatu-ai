"""verify_pass._call_opus — integration with the Anthropic SDK.

Mocks the SDK client so we don't burn API credits, but still exercises the
real json parsing / fence stripping / schema-defaulting code.

Gating: ENABLE_VERIFY_PASS must remain OFF by default; covered by
test_returns_empty_when_disabled in test_verify_pass.py.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from extractor.verify_pass import _call_opus


def _fake_response(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    msg = MagicMock()
    msg.content = [block]
    return msg


def test_call_opus_parses_strict_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_response(
        '{"corrections":[{"pozicija_id":"p1","suggested_value":10.5,'
        '"reason":"foo","confidence":"high"}]}'
    )
    with patch("extractor.verify_pass.anthropic.Anthropic", return_value=fake_client):
        out = _call_opus("verify this")
    assert isinstance(out, dict)
    assert len(out["corrections"]) == 1
    assert out["corrections"][0]["pozicija_id"] == "p1"


def test_call_opus_strips_fenced_json(monkeypatch):
    """Model occasionally wraps JSON in ```json fences despite the system
    prompt. We must tolerate that without raising."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_response(
        '```json\n{"corrections":[]}\n```'
    )
    with patch("extractor.verify_pass.anthropic.Anthropic", return_value=fake_client):
        out = _call_opus("verify this")
    assert out == {"corrections": []}


def test_call_opus_defaults_missing_corrections_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_response('{"other":"value"}')
    with patch("extractor.verify_pass.anthropic.Anthropic", return_value=fake_client):
        out = _call_opus("verify this")
    assert out["corrections"] == []
    assert out["other"] == "value"


def test_call_opus_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        _call_opus("verify this")


def test_call_opus_uses_opus_model(monkeypatch):
    """Smoke: confirm we're calling Opus 4.7, not the smaller models."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_response('{"corrections":[]}')
    with patch("extractor.verify_pass.anthropic.Anthropic", return_value=fake_client):
        _call_opus("verify this")
    kwargs = fake_client.messages.create.call_args.kwargs
    assert "opus" in kwargs["model"].lower()


def test_call_opus_invalid_json_raises(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_response("not json at all")
    with patch("extractor.verify_pass.anthropic.Anthropic", return_value=fake_client):
        with pytest.raises(Exception):  # noqa: BLE001 — we just need it to surface
            _call_opus("verify this")
