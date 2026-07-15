"""Fix 5 — Unbounded per-request loops get DoS caps.

/recompute-interior caps len(payload.patalpos) at 500; /detect-scale-hint caps
page iteration at 200. Over-cap → HTTP 400 (Lithuanian message). Normal input
is unaffected.
"""
from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

import main


# ── /recompute-interior patalpos cap ────────────────────────────────────────
def test_recompute_over_cap_rejected(monkeypatch):
    # Bypass auth/billing — we are testing the length gate that follows it.
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "dev"})
    c = TestClient(main.app)
    payload = {"patalpos": [{} for _ in range(501)]}
    r = c.post("/recompute-interior", json=payload)
    assert r.status_code == 400, r.text
    assert "patal" in r.json()["detail"].lower()


def test_recompute_normal_input_not_capped(monkeypatch):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "dev"})
    c = TestClient(main.app)
    payload = {
        "patalpos": [
            {"nr": "101", "pavadinimas": "Kambarys", "paskirtis": "kambarys",
             "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.7},
        ],
    }
    r = c.post("/recompute-interior", json=payload)
    assert r.status_code != 400, r.text  # not rejected by the cap


# ── /detect-scale-hint page cap ─────────────────────────────────────────────
class _FakePage:
    def extract_text(self):
        return ""


class _FakePDF:
    def __init__(self, n):
        self.pages = [_FakePage() for _ in range(n)]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_detect_scale_over_page_cap_rejected(monkeypatch):
    import pdfplumber
    monkeypatch.setattr(main._auth, "require_user", lambda request: {"id": "dev"})
    monkeypatch.setattr(pdfplumber, "open", lambda *a, **k: _FakePDF(201))
    c = TestClient(main.app)
    b64 = base64.b64encode(b"%PDF-1.4 fake").decode()
    r = c.post("/detect-scale-hint", json={"pdf_b64": b64})
    assert r.status_code == 400, r.text
    assert "puslapi" in r.json()["detail"].lower()


def test_detect_scale_under_cap_ok(monkeypatch):
    import pdfplumber
    monkeypatch.setattr(main._auth, "require_user", lambda request: {"id": "dev"})
    monkeypatch.setattr(pdfplumber, "open", lambda *a, **k: _FakePDF(2))
    c = TestClient(main.app)
    b64 = base64.b64encode(b"%PDF-1.4 fake").decode()
    r = c.post("/detect-scale-hint", json={"pdf_b64": b64})
    assert r.status_code == 200, r.text
    assert r.json()["found"] is False
