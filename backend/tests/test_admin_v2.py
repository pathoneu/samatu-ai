"""Admin Dashboard v2 — operational cockpit backend (owner-authorized).

Covers the new /api/admin/v2 router: analytics time series, accurate cost
monitor, paginated + searchable user management, disable/enable with guardrails,
system health, and CSV export (injection-sanitized).

CRITICAL money invariant pinned by these tests: ALL cost figures come from
usage_events.cost_eur (the complete per-call meter incl. sub-readers), NEVER
from extractions.cost_eur (PASS-1-ONLY). A test seeds a divergent value into
extractions and asserts the admin numbers ignore it.

Auth: every endpoint requires an admin (403 non-admin, 401 anon).

Import order mirrors test_export_auth.py: `from main import app` FIRST so the
.env load runs before auth.py freezes AUTH_DISABLED.
"""
import csv
import io

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402

_PW = "passw0rd123"


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "admin_v2.db")
    # Force real auth even if the dev bypass env var is set on the host.
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    # (The login rate-limit bucket is reset before every test by an autouse
    # fixture in conftest.py, so this login-heavy file stays under the 30/min cap.)
    db.init_schema()
    db._migrate_schema()


def _mk_admin(email="admin@x.lt"):
    return db.create_user(email, auth.hash_password(_PW), name="Admin", is_admin=True)


def _mk_user(email, name="User", company="Statyba UAB"):
    return db.create_user(email, auth.hash_password(_PW), name=name, company_name=company)


def _logged_in(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _seed_usage(user_id, cost_eur, kind="extract-interior", model="claude-opus-4-8",
                created_at=None):
    """Insert one usage_events row directly (bypasses token pricing so the test
    controls the exact euro figure)."""
    import uuid
    with db._conn() as c:
        c.execute(
            """INSERT INTO usage_events
                 (id, user_id, kind, input_tokens, output_tokens,
                  cache_read_tokens, cost_eur, model, created_at)
               VALUES (?, ?, ?, 0, 0, 0, ?, ?, ?)""",
            (uuid.uuid4().hex, user_id, kind, cost_eur, model,
             created_at or db._now_iso()),
        )


def _seed_extraction(project_id, cost_eur):
    """Insert an extractions row with a DELIBERATELY WRONG cost so we can prove
    the admin cost numbers read usage_events, not extractions."""
    import uuid
    with db._conn() as c:
        c.execute(
            """INSERT INTO extractions
                 (id, project_id, raw_response, cost_eur, extracted_at)
               VALUES (?, ?, '{}', ?, ?)""",
            (uuid.uuid4().hex, project_id, cost_eur, db._now_iso()),
        )


# ── auth gate ────────────────────────────────────────────────────────────────

_ENDPOINTS = [
    "/api/admin/v2/analytics",
    "/api/admin/v2/cost-monitor",
    "/api/admin/v2/users",
    "/api/admin/v2/system-health",
    "/api/admin/v2/export/users.csv",
    "/api/admin/v2/export/cost.csv",
    "/api/admin/v2/audit-log",
]


@pytest.mark.parametrize("path", _ENDPOINTS)
def test_endpoints_reject_anonymous_401(tmp_path, monkeypatch, path):
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    r = TestClient(app).get(path)
    assert r.status_code == 401, r.text


@pytest.mark.parametrize("path", _ENDPOINTS)
def test_endpoints_reject_non_admin_403(tmp_path, monkeypatch, path):
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    _mk_user("plain@x.lt")
    r = _logged_in("plain@x.lt").get(path)
    assert r.status_code == 403, r.text


def test_disable_enable_reject_non_admin_403(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    victim = _mk_user("victim@x.lt")
    _mk_user("plain@x.lt")
    c = _logged_in("plain@x.lt")
    assert c.post(f"/api/admin/v2/users/{victim['id']}/disable").status_code == 403
    assert c.post(f"/api/admin/v2/users/{victim['id']}/enable").status_code == 403


# ── analytics ────────────────────────────────────────────────────────────────

def test_analytics_shape_and_totals(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    u = _mk_user("u1@x.lt")
    # two extraction usage events today + one non-extract event
    _seed_usage(u["id"], 1.50, kind="extract-interior")
    _seed_usage(u["id"], 0.50, kind="extract-interior")
    _seed_usage(u["id"], 0.10, kind="vision_fill")  # not an extraction
    r = _logged_in("admin@x.lt").get("/api/admin/v2/analytics?days=30")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "series" in body and isinstance(body["series"], list)
    assert "totals" in body and "deltas" in body
    row = body["series"][0]
    for key in ("date", "signups", "projects", "extractions", "cost_eur", "revenue_eur"):
        assert key in row, f"missing {key} in series row"
    # cost total = sum of ALL usage_events (2.10), extraction count = 2
    assert body["totals"]["cost_eur"] == pytest.approx(2.10, abs=0.01)
    assert body["totals"]["extractions"] == 2


def test_analytics_cost_uses_usage_events_not_extractions(tmp_path, monkeypatch):
    """Money invariant: extractions.cost_eur (PASS-1-ONLY) must be ignored."""
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    u = _mk_user("u1@x.lt")
    db.upsert_project("p1", {"name": "P1", "tipas": "interjeras"}, user_id=u["id"])
    _seed_extraction("p1", cost_eur=99.99)      # WRONG (pass-1 only)
    _seed_usage(u["id"], 3.00, kind="extract-interior")  # the true full cost
    r = _logged_in("admin@x.lt").get("/api/admin/v2/analytics?days=30")
    body = r.json()
    assert body["totals"]["cost_eur"] == pytest.approx(3.00, abs=0.01)
    assert body["totals"]["cost_eur"] != pytest.approx(99.99, abs=0.01)


# ── cost monitor ─────────────────────────────────────────────────────────────

def test_cost_monitor_shape_and_top_users(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    big = _mk_user("big@x.lt")
    small = _mk_user("small@x.lt")
    _seed_usage(big["id"], 4.00, model="claude-opus-4-8")
    _seed_usage(big["id"], 2.00, model="fable-5")
    _seed_usage(small["id"], 0.25, model="claude-opus-4-8")
    r = _logged_in("admin@x.lt").get("/api/admin/v2/cost-monitor?days=30")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_cost_eur"] == pytest.approx(6.25, abs=0.01)
    assert "avg_cost_per_extraction_eur" in body
    assert "today_cost_eur" in body
    # top users sorted by spend, biggest first
    top = body["top_users"]
    assert top[0]["email"] == "big@x.lt"
    assert top[0]["spend_eur"] == pytest.approx(6.00, abs=0.01)
    # per-model breakdown present
    models = {m["model"]: m["cost_eur"] for m in body["by_model"]}
    assert models["claude-opus-4-8"] == pytest.approx(4.25, abs=0.01)
    assert models["fable-5"] == pytest.approx(2.00, abs=0.01)


def test_cost_monitor_threshold_alert(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("SAMATU_ADMIN_COST_ALERT_EUR", "5.0")
    _mk_admin()
    spender = _mk_user("spender@x.lt")
    calm = _mk_user("calm@x.lt")
    _seed_usage(spender["id"], 6.00)   # over threshold today
    _seed_usage(calm["id"], 1.00)      # under
    r = _logged_in("admin@x.lt").get("/api/admin/v2/cost-monitor?days=30")
    body = r.json()
    alerts = {a["email"] for a in body["alerts"]}
    assert "spender@x.lt" in alerts
    assert "calm@x.lt" not in alerts
    assert body["alert_threshold_eur"] == pytest.approx(5.0, abs=0.001)


# ── users management ─────────────────────────────────────────────────────────

def test_users_pagination_and_spend(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    for i in range(5):
        _mk_user(f"user{i}@x.lt", name=f"User {i}")
    spender = db.get_user_by_email("user0@x.lt")
    _seed_usage(spender["id"], 2.50)
    db.upsert_project("proj-a", {"name": "A", "tipas": "interjeras"}, user_id=spender["id"])
    c = _logged_in("admin@x.lt")
    r = c.get("/api/admin/v2/users?page=1&limit=3")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["page"] == 1 and body["limit"] == 3
    assert body["total"] == 6            # 5 users + 1 admin
    assert len(body["rows"]) == 3
    # row shape
    row = body["rows"][0]
    for key in ("id", "email", "name", "company_name", "company_code", "plan",
                "plan_status", "is_admin", "is_active", "created_at",
                "last_login_at", "project_count", "total_spend_eur"):
        assert key in row, f"missing {key} in user row"
    # page 2 returns the remainder
    r2 = c.get("/api/admin/v2/users?page=2&limit=3")
    assert len(r2.json()["rows"]) == 3


def test_users_search_matches_email_name_company(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    _mk_user("alice@acme.lt", name="Alice", company="Acme Statyba")
    _mk_user("bob@other.lt", name="Bob", company="Kita UAB")
    c = _logged_in("admin@x.lt")
    # by email fragment
    assert {r["email"] for r in c.get("/api/admin/v2/users?search=acme").json()["rows"]} == {"alice@acme.lt"}
    # by name
    assert {r["email"] for r in c.get("/api/admin/v2/users?search=Bob").json()["rows"]} == {"bob@other.lt"}
    # by company
    assert {r["email"] for r in c.get("/api/admin/v2/users?search=Kita").json()["rows"]} == {"bob@other.lt"}


def test_users_search_is_parameterized_no_injection(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    _mk_user("real@x.lt")
    c = _logged_in("admin@x.lt")
    # A classic injection payload must be treated as a literal search string
    # (matches nothing) and must NOT drop the users table.
    r = c.get("/api/admin/v2/users", params={"search": "'; DROP TABLE users;--"})
    assert r.status_code == 200, r.text
    assert r.json()["rows"] == []
    # table still intact
    assert c.get("/api/admin/v2/users").json()["total"] >= 2


# ── disable / enable + guardrails ────────────────────────────────────────────

def test_disable_and_enable_toggles_is_active(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    victim = _mk_user("victim@x.lt")
    c = _logged_in("admin@x.lt")
    assert c.post(f"/api/admin/v2/users/{victim['id']}/disable").status_code == 200
    assert db.get_user_by_id(victim["id"])["is_active"] == 0
    assert c.post(f"/api/admin/v2/users/{victim['id']}/enable").status_code == 200
    assert db.get_user_by_id(victim["id"])["is_active"] == 1


def test_admin_cannot_disable_self(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    admin = _mk_admin()
    c = _logged_in("admin@x.lt")
    r = c.post(f"/api/admin/v2/users/{admin['id']}/disable")
    assert r.status_code == 400, r.text
    assert db.get_user_by_id(admin["id"])["is_active"] == 1


def test_admin_cannot_disable_another_admin(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _mk_admin("admin1@x.lt")
    admin2 = _mk_admin("admin2@x.lt")
    c = _logged_in("admin1@x.lt")
    r = c.post(f"/api/admin/v2/users/{admin2['id']}/disable")
    assert r.status_code == 400, r.text
    assert db.get_user_by_id(admin2["id"])["is_active"] == 1


def test_disabled_user_cannot_login(tmp_path, monkeypatch):
    """The whole point of 'disable': an inactive user must be refused at login."""
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    victim = _mk_user("victim@x.lt")
    _logged_in("admin@x.lt").post(f"/api/admin/v2/users/{victim['id']}/disable")
    # fresh client, correct password → still rejected
    r = TestClient(app).post(
        "/api/auth/login", json={"email": "victim@x.lt", "password": _PW})
    assert r.status_code == 401, r.text


def test_disabled_user_existing_session_is_rejected(tmp_path, monkeypatch):
    """A user disabled mid-session must lose access on the next request."""
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    victim = _mk_user("victim@x.lt")
    vc = _logged_in("victim@x.lt")
    assert vc.get("/api/auth/me").status_code == 200
    _logged_in("admin@x.lt").post(f"/api/admin/v2/users/{victim['id']}/disable")
    assert vc.get("/api/auth/me").status_code == 401


# ── system health ────────────────────────────────────────────────────────────

def test_system_health_shape(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    u = _mk_user("u@x.lt")
    _seed_usage(u["id"], 1.0, kind="extract-interior")
    r = _logged_in("admin@x.lt").get("/api/admin/v2/system-health")
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("totals", "events_by_kind", "db_size_bytes",
                "recent_activity", "error_log_tail"):
        assert key in body, f"missing {key}"
    assert body["totals"]["users"] >= 2
    assert body["db_size_bytes"] > 0
    # no persisted error log in this app → empty list + a note
    assert body["error_log_tail"] == []
    assert "note" in body


# ── CSV export ───────────────────────────────────────────────────────────────

def test_export_users_csv(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    _mk_user("csvuser@x.lt", name="Csv User", company="CsvCo")
    r = _logged_in("admin@x.lt").get("/api/admin/v2/export/users.csv")
    assert r.status_code == 200, r.text
    assert "text/csv" in r.headers["content-type"]
    assert "attachment" in r.headers.get("content-disposition", "")
    rows = list(csv.reader(io.StringIO(r.text)))
    header = rows[0]
    assert "email" in header and "total_spend_eur" in header
    emails = {row[header.index("email")] for row in rows[1:]}
    assert "csvuser@x.lt" in emails


def test_export_cost_csv(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    u = _mk_user("u@x.lt")
    _seed_usage(u["id"], 2.0, kind="extract-interior")
    r = _logged_in("admin@x.lt").get("/api/admin/v2/export/cost.csv?days=30")
    assert r.status_code == 200, r.text
    assert "text/csv" in r.headers["content-type"]
    rows = list(csv.reader(io.StringIO(r.text)))
    header = rows[0]
    for col in ("date", "signups", "projects", "extractions", "cost_eur", "revenue_eur"):
        assert col in header, f"missing {col} in cost csv header"


def test_export_users_csv_sanitizes_injection(tmp_path, monkeypatch):
    """CSV injection: a name/company starting with =,+,-,@ must be neutralised
    with a leading single quote (spreadsheet_safety), same class as F6/P3."""
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    # name is a formula-trigger payload
    db.create_user("evil@x.lt", auth.hash_password(_PW),
                   name="=HYPERLINK(\"http://evil\",\"x\")", company_name="+SUM(A1:A9)")
    r = _logged_in("admin@x.lt").get("/api/admin/v2/export/users.csv")
    assert r.status_code == 200, r.text
    # Parse the CSV properly (RFC 4180 quoting) and inspect the actual cells.
    rows = list(csv.reader(io.StringIO(r.text)))
    header = rows[0]
    evil = next(row for row in rows[1:]
                if row[header.index("email")] == "evil@x.lt")
    name = evil[header.index("name")]
    company = evil[header.index("company_name")]
    # Every risky cell must be neutralised with a leading single quote so the
    # spreadsheet renders it as literal text instead of evaluating the formula.
    assert name.startswith("'="), name
    assert company.startswith("'+"), company


# ── admin audit log ──────────────────────────────────────────────────────────

def test_disable_writes_audit_row(tmp_path, monkeypatch):
    """The whole point of the audit trail: disabling a user records WHO did it,
    to WHOM, and WHAT action — none of which was captured before."""
    _isolate(tmp_path, monkeypatch)
    admin = _mk_admin()
    victim = _mk_user("victim@x.lt")
    c = _logged_in("admin@x.lt")
    assert c.post(f"/api/admin/v2/users/{victim['id']}/disable").status_code == 200
    actions = db.list_admin_actions()
    assert len(actions) == 1
    row = actions[0]
    assert row["action"] == "user.disable"
    assert row["actor_user_id"] == admin["id"]
    assert row["target_user_id"] == victim["id"]
    assert row["created_at"]


def test_enable_writes_audit_row_newest_first(tmp_path, monkeypatch):
    """Enable also logs; list returns newest action first even when both land in
    the same wall-clock second (ordering must tie-break on insertion order)."""
    _isolate(tmp_path, monkeypatch)
    admin = _mk_admin()
    victim = _mk_user("victim@x.lt")
    c = _logged_in("admin@x.lt")
    c.post(f"/api/admin/v2/users/{victim['id']}/disable")
    c.post(f"/api/admin/v2/users/{victim['id']}/enable")
    actions = db.list_admin_actions()
    assert [a["action"] for a in actions] == ["user.enable", "user.disable"]
    assert actions[0]["actor_user_id"] == admin["id"]
    assert actions[0]["target_user_id"] == victim["id"]


def test_blocked_action_writes_no_audit_row(tmp_path, monkeypatch):
    """A guardrail-rejected action (disabling yourself / another admin) changes
    nothing, so it must leave NO audit row — the log records performed actions,
    not attempts."""
    _isolate(tmp_path, monkeypatch)
    admin1 = _mk_admin("admin1@x.lt")
    admin2 = _mk_admin("admin2@x.lt")
    c = _logged_in("admin1@x.lt")
    assert c.post(f"/api/admin/v2/users/{admin1['id']}/disable").status_code == 400
    assert c.post(f"/api/admin/v2/users/{admin2['id']}/disable").status_code == 400
    assert db.list_admin_actions() == []


def test_record_and_list_admin_actions_helper(tmp_path, monkeypatch):
    """DB-level contract for the helpers: record persists actor/action/target/
    detail; list is newest-first and honours `limit`."""
    _isolate(tmp_path, monkeypatch)
    admin = _mk_admin()
    target = _mk_user("t@x.lt")
    db.record_admin_action(admin["id"], "user.disable", target["id"], detail="t@x.lt")
    db.record_admin_action(admin["id"], "user.enable", target["id"])
    limited = db.list_admin_actions(limit=1)
    assert len(limited) == 1                       # limit honoured
    assert limited[0]["action"] == "user.enable"   # newest first
    rows = db.list_admin_actions()
    disable_row = next(r for r in rows if r["action"] == "user.disable")
    assert disable_row["actor_user_id"] == admin["id"]
    assert disable_row["target_user_id"] == target["id"]
    assert disable_row["detail"] == "t@x.lt"


def test_audit_log_endpoint_returns_enriched_rows(tmp_path, monkeypatch):
    """GET /audit-log surfaces the trail read-only, newest first, and joins in
    actor/target emails for a human-readable dashboard."""
    _isolate(tmp_path, monkeypatch)
    _mk_admin()
    victim = _mk_user("victim@x.lt")
    c = _logged_in("admin@x.lt")
    c.post(f"/api/admin/v2/users/{victim['id']}/disable")
    r = c.get("/api/admin/v2/audit-log")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body.get("rows"), list) and body["rows"]
    top = body["rows"][0]
    assert top["action"] == "user.disable"
    assert top["actor_email"] == "admin@x.lt"
    assert top["target_email"] == "victim@x.lt"
