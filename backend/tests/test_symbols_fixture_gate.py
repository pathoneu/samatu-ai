"""2026-07-27 audit finding 10 — /detect-symbols?fixture= was not ownership-gated.

The route requires a billable user (2026-06-19 fix), but the fixture branch of
_resolve_pdf_bytes returns the committed contractor PDF for ANY project_id, with
no ownership check — so any logged-in user could read a real project's drawing
through it (and burn Vision spend on it). Same convention as api/room_graph.py:
the fixture branch is dev/demo only; in production the ?fixture= param is ignored
and the request falls through to the owner-scoped DB path.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api import symbols as sym  # noqa: E402


class _Req:
    """Minimal stand-in for fastapi.Request — _resolve_pdf_bytes only passes it
    through to auth/db helpers, both of which are patched here."""


def test_fixture_served_outside_production(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    if not sym.FIXTURES["berzas"].exists():
        pytest.skip("berzas fixture PDF not present in this checkout")
    data = sym._resolve_pdf_bytes(_Req(), "any-project-id", "berzas")
    assert data[:4] == b"%PDF"


def test_fixture_ignored_in_production(monkeypatch):
    """ENV=production → fall through to the authenticated, owner-scoped path,
    which 404s for a project the caller does not own."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setattr(sym._auth, "require_user",
                        lambda request: {"id": "attacker", "is_admin": False})
    monkeypatch.setattr(sym._db, "get_project", lambda pid, user_id=None: None)

    with pytest.raises(HTTPException) as e:
        sym._resolve_pdf_bytes(_Req(), "victim-project-id", "berzas")
    assert e.value.status_code == 404
    assert "berzas" not in str(e.value.detail)      # no fixture bytes, no fixture hint


def test_production_owner_path_still_serves_own_project(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setattr(sym._auth, "require_user",
                        lambda request: {"id": "owner", "is_admin": False})
    monkeypatch.setattr(sym._db, "get_project",
                        lambda pid, user_id=None: {"id": pid})
    monkeypatch.setattr(sym._db, "get_project_pdf_bytes",
                        lambda pid, user_id=None: b"%PDF-own", raising=False)
    assert sym._resolve_pdf_bytes(_Req(), "own-project", "berzas") == b"%PDF-own"


def test_unknown_fixture_still_404s(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    with pytest.raises(HTTPException) as e:
        sym._resolve_pdf_bytes(_Req(), "p", "nera-tokio")
    assert e.value.status_code == 404
