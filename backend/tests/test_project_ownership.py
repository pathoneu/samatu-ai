"""Project ownership barrier + OAuth open-redirect guard (2026-06-19 security hunt).

The old upsert_project guard had an `existing["user_id"] and` short-circuit that
SKIPPED the ownership check for NULL-owner (pre-auth single-tenant) rows, letting
any logged-in user overwrite/wipe an orphan project by id. And the Google OAuth
`?next=` param was redirected to verbatim (open redirect → phishing).
"""
import db
import pytest


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "own.db")
    db.init_schema()
    db._migrate_schema()


def test_owner_can_update_own_project(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    a = db.create_user("a@x.lt", "h", name="A")
    db.upsert_project("p1", {"name": "v1", "tipas": "interjeras"}, user_id=a["id"])
    db.upsert_project("p1", {"name": "v2", "tipas": "interjeras"}, user_id=a["id"])
    assert db.get_project("p1", user_id=a["id"])["name"] == "v2"


def test_cannot_overwrite_other_users_project(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    a = db.create_user("a@x.lt", "h", name="A")
    b = db.create_user("b@x.lt", "h", name="B")
    db.upsert_project("p1", {"name": "A's", "tipas": "interjeras"}, user_id=a["id"])
    with pytest.raises(PermissionError):
        db.upsert_project("p1", {"name": "B steals", "tipas": "interjeras"}, user_id=b["id"])
    assert db.get_project("p1", user_id=a["id"])["name"] == "A's"  # untouched


def test_authed_user_cannot_overwrite_orphan_project(tmp_path, monkeypatch):
    """The core bug: a NULL-owner (pre-auth) project must NOT be silently
    overwritable by any logged-in user who knows its id."""
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("orphan", {"name": "Founder secret", "tipas": "interjeras"}, user_id=None)
    attacker = db.create_user("att@x.lt", "h", name="Att")
    with pytest.raises(PermissionError):
        db.upsert_project("orphan", {"name": "WIPED", "tipas": "interjeras"}, user_id=attacker["id"])


def test_anonymous_mode_still_writes(tmp_path, monkeypatch):
    """SAMATU_AUTH_DISABLED single-tenant mode (user_id=None) must still work."""
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", {"name": "v1", "tipas": "interjeras"}, user_id=None)
    db.upsert_project("p1", {"name": "v2", "tipas": "interjeras"}, user_id=None)
    assert db.get_project("p1")["name"] == "v2"


def test_backfill_assigns_orphans_to_bootstrap_admin(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    admin = db.create_user("admin@x.lt", "h", name="Admin", is_admin=True)
    db.upsert_project("orphan", {"name": "pre-auth", "tipas": "interjeras"}, user_id=None)
    assert db._backfill_orphan_project_owners() == 1
    assert db.get_project("orphan", user_id=admin["id"])["name"] == "pre-auth"
    # idempotent — nothing left to reassign
    assert db._backfill_orphan_project_owners() == 0


def test_safe_next_path_blocks_open_redirect():
    from main import _safe_next_path
    # same-origin relative paths pass through
    assert _safe_next_path("/dashboard") == "/dashboard"
    assert _safe_next_path("/project/abc?x=1") == "/project/abc?x=1"
    # off-origin / scheme / scheme-relative / tricks → fall back to "/"
    for bad in ("https://evil.example", "//evil.example", "/\\evil.example",
                "javascript:alert(1)", "http://x", "", None, "evil.example"):
        assert _safe_next_path(bad) == "/", bad
