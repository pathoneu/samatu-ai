# backend/tests/test_verify_pass.py
"""Sprint 3 Section 6: self-verify pass produces advisory corrections."""
from unittest.mock import patch
from extractor.verify_pass import run_verify_pass, VerifyResult


def test_returns_corrections_list(monkeypatch):
    monkeypatch.setenv("ENABLE_VERIFY_PASS", "1")
    fake_response = {
        "corrections": [
            {"pozicija_id": "poz-1", "suggested_value": 18.5,
             "reason": "Vonioje plytelių zona 2.0m × 11.2m perimetras = 22.4 m², ne 23.4",
             "confidence": "high"},
        ],
    }
    with patch("extractor.verify_pass._call_opus", return_value=fake_response):
        result = run_verify_pass(rooms=[], pozicijos=[
            {"id": "poz-1", "kiekis": 23.4, "vnt": "m2", "aprasymas": "Sienų plytelės"},
        ])
    assert isinstance(result, VerifyResult)
    assert len(result.corrections) == 1
    assert result.corrections[0]["pozicija_id"] == "poz-1"
    assert result.corrections[0]["suggested_value"] == 18.5


def test_returns_empty_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_VERIFY_PASS", "0")
    result = run_verify_pass(rooms=[], pozicijos=[
        {"id": "poz-1", "kiekis": 23.4, "vnt": "m2", "aprasymas": "X"},
    ])
    assert result.corrections == []


def test_handles_anthropic_error_gracefully(monkeypatch):
    monkeypatch.setenv("ENABLE_VERIFY_PASS", "1")
    with patch("extractor.verify_pass._call_opus", side_effect=RuntimeError("anthropic 500")):
        # Should not raise; returns empty corrections
        result = run_verify_pass(rooms=[], pozicijos=[
            {"id": "poz-1", "kiekis": 23.4, "vnt": "m2", "aprasymas": "X"},
        ])
    assert result.corrections == []
    assert "anthropic 500" in (result.error or "")
