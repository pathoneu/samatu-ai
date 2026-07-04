"""SQLite-backed project storage for Sąmatų AI.

Replaces frontend localStorage as the source of truth for projects.
Frontend becomes a write-through cache: on edit, write to localStorage
(instant) AND POST to backend (durable, cross-device).

Schema:
- projects:    id, name, company_name, tipas, archetipas, status, data (JSON), created_at, updated_at
- extractions: id, project_id, pdf_sha256, pdf_size, page_count, raw_response (JSON), tokens, cost, elapsed_s
- corrections: project_id, room_nr, field_path, old_value, new_value, source, occurred_at — audit log
                for future learning-loop / prompt iteration

No auth yet — single-tenant. When auth lands, add user_id to projects.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# DB file lives outside repo root (gitignored). Override via env if needed.
_DB_PATH = Path(os.environ.get("SAMATU_DB_PATH",
                                Path(__file__).resolve().parent / "data" / "samatu.db"))
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_DB_LOCK = threading.Lock()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@contextmanager
def _conn():
    """Get a SQLite connection (per-call, thread-safe via timeout + lock)."""
    with _DB_LOCK:
        c = sqlite3.connect(_DB_PATH, timeout=10.0, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA foreign_keys=ON")
        try:
            yield c
        finally:
            c.close()


def init_schema() -> None:
    """Create tables if missing. Safe to call repeatedly (idempotent)."""
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            TEXT PRIMARY KEY,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name          TEXT,
                company_name  TEXT,
                is_admin      INTEGER NOT NULL DEFAULT 0,
                is_active     INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT NOT NULL,
                last_login_at TEXT,
                session_version INTEGER NOT NULL DEFAULT 1  -- F2: logout/pw-change nonce
            );
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

            CREATE TABLE IF NOT EXISTS projects (
                id           TEXT PRIMARY KEY,
                user_id      TEXT REFERENCES users(id) ON DELETE CASCADE,
                name         TEXT NOT NULL,
                company_name TEXT,
                tipas        TEXT NOT NULL,
                archetipas   TEXT,
                status       TEXT DEFAULT 'ready',
                bendras_plotas_m2 REAL,
                vat_rate     REAL DEFAULT 21,
                data         TEXT NOT NULL,            -- JSON blob
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC);
            -- idx_projects_user created in _migrate_schema after column exists

            CREATE TABLE IF NOT EXISTS extractions (
                id              TEXT PRIMARY KEY,
                project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                pdf_sha256      TEXT,
                pdf_size_bytes  INTEGER,
                pdf_page_count  INTEGER,
                raw_response    TEXT NOT NULL,         -- JSON blob
                input_tokens    INTEGER,
                output_tokens   INTEGER,
                cache_read_tokens INTEGER,
                elapsed_s       REAL,
                cost_eur        REAL,
                model           TEXT,                  -- W1.1 (2026-07-03)
                extracted_at    TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_extr_project ON extractions(project_id);

            -- usage_events: user-keyed Vision-cost ledger for the per-user spend
            -- cap. Decoupled from projects on purpose — extraction happens BEFORE
            -- the project row is created (the frontend creates the project after
            -- the extraction returns), so the extractions table (project_id FK)
            -- can never be written at extract time. This ledger CAN. (2026-06-19)
            CREATE TABLE IF NOT EXISTS usage_events (
                id                TEXT PRIMARY KEY,
                user_id           TEXT NOT NULL,
                kind              TEXT,
                input_tokens      INTEGER,
                output_tokens     INTEGER,
                cache_read_tokens INTEGER,
                cost_eur          REAL,
                model             TEXT,                -- W1.1 (2026-07-03)
                created_at        TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_usage_user_time ON usage_events(user_id, created_at);

            CREATE TABLE IF NOT EXISTS corrections (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                room_nr      TEXT,
                field_path   TEXT NOT NULL,
                old_value    TEXT,                      -- JSON-stringified
                new_value    TEXT,                      -- JSON-stringified
                source       TEXT,
                note         TEXT,
                occurred_at  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_corr_project ON corrections(project_id);
            CREATE INDEX IF NOT EXISTS idx_corr_field ON corrections(field_path);
            CREATE INDEX IF NOT EXISTS idx_corr_occurred ON corrections(occurred_at);
        """)


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(email: str, password_hash: str, name: str | None = None,
                 company_name: str | None = None, is_admin: bool = False) -> dict:
    """Insert new user. Caller is responsible for password hashing."""
    import uuid
    user_id = str(uuid.uuid4())
    now = _now_iso()
    with _conn() as c:
        c.execute("""
            INSERT INTO users (id, email, password_hash, name, company_name,
                               is_admin, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (user_id, email.lower().strip(), password_hash, name, company_name,
              1 if is_admin else 0, now))
    return get_user_by_id(user_id) or {}


def get_user_by_email(email: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
        return dict(row) if row else None


def get_user_by_google_sub(google_sub: str) -> dict | None:
    """Look up a user by their Google `sub` (stable account identifier).
    Used by the OAuth callback to find an existing OAuth user."""
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE google_sub = ?", (google_sub,)).fetchone()
        return dict(row) if row else None


def create_user_oauth(email: str, google_sub: str, name: str | None = None,
                      avatar_url: str | None = None, is_admin: bool = False) -> dict:
    """Create a user with no password (OAuth-only). password_hash is set to
    a sentinel '!oauth' so the column NOT NULL constraint is satisfied while
    making clear this user cannot log in via password. verify_password() will
    always return False for these accounts."""
    import uuid
    user_id = str(uuid.uuid4())
    now = _now_iso()
    with _conn() as c:
        c.execute("""
            INSERT INTO users (id, email, password_hash, name, company_name,
                               is_admin, is_active, created_at,
                               google_sub, avatar_url)
            VALUES (?, ?, '!oauth', ?, NULL, ?, 1, ?, ?, ?)
        """, (user_id, email.lower().strip(), name,
              1 if is_admin else 0, now, google_sub, avatar_url))
    return get_user_by_id(user_id) or {}


def link_google_to_user(user_id: str, google_sub: str, avatar_url: str | None = None) -> None:
    """When a Google login matches an existing email-password user, link the
    Google account to the existing user instead of creating a duplicate."""
    with _conn() as c:
        c.execute(
            "UPDATE users SET google_sub = ?, avatar_url = COALESCE(?, avatar_url) WHERE id = ?",
            (google_sub, avatar_url, user_id),
        )


def get_user_by_id(user_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def update_user_login(user_id: str) -> None:
    with _conn() as c:
        c.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (_now_iso(), user_id))


def bump_session_version(user_id: str) -> int:
    """F2 (2026-07-04 pentest): invalidate every existing session for this user
    by incrementing the session_version nonce. Called on logout and on
    change-password. Returns the new version. require_user rejects any session
    cookie whose embedded 'sv' no longer matches, so a captured pre-logout cookie
    stops replaying immediately."""
    with _conn() as c:
        c.execute(
            "UPDATE users SET session_version = COALESCE(session_version, 1) + 1 WHERE id = ?",
            (user_id,),
        )
        row = c.execute(
            "SELECT session_version FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return int(row["session_version"]) if row else 1


def list_users(admin_only: bool = False) -> list[dict]:
    """Admin endpoint — returns user summaries (no password_hash)."""
    with _conn() as c:
        sql = """SELECT id, email, name, company_name, is_admin, is_active,
                        created_at, last_login_at
                   FROM users
               ORDER BY created_at DESC"""
        rows = c.execute(sql).fetchall()
        return [dict(r) for r in rows]


# ── Projects ──────────────────────────────────────────────────────────────────

def list_projects(user_id: str | None = None) -> list[dict]:
    """Return summary list (no full data blob).
    If user_id given — only that user's projects. None = all (admin only)."""
    with _conn() as c:
        if user_id:
            rows = c.execute("""
                SELECT id, user_id, name, company_name, tipas, archetipas, status,
                       bendras_plotas_m2, vat_rate, created_at, updated_at
                  FROM projects
                 WHERE user_id = ?
              ORDER BY updated_at DESC
            """, (user_id,)).fetchall()
        else:
            rows = c.execute("""
                SELECT id, user_id, name, company_name, tipas, archetipas, status,
                       bendras_plotas_m2, vat_rate, created_at, updated_at
                  FROM projects
              ORDER BY updated_at DESC
            """).fetchall()
        return [dict(r) for r in rows]


def get_project(project_id: str, user_id: str | None = None) -> dict | None:
    """Get project. If user_id given — enforce ownership (returns None if not match)."""
    with _conn() as c:
        if user_id:
            row = c.execute("SELECT * FROM projects WHERE id = ? AND user_id = ?",
                            (project_id, user_id)).fetchone()
        else:
            row = c.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            data = json.loads(d.pop("data") or "{}")
        except Exception:
            data = {}
        return {**data, **{k: v for k, v in d.items() if v is not None}}


def upsert_project(project_id: str, payload: dict, user_id: str | None = None) -> dict:
    """Insert or full-replace. user_id stored on create; on update, ownership
    is checked first (raises if mismatch)."""
    now = _now_iso()
    name = payload.get("name") or "Naujas projektas"
    tipas = payload.get("tipas") or "interjeras"
    blob = json.dumps(payload, ensure_ascii=False)
    with _conn() as c:
        existing = c.execute(
            "SELECT created_at, user_id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if existing:
            # Ownership barrier (2026-06-19 security hunt): when the caller is
            # authenticated, reject a write to a project owned by anyone else —
            # INCLUDING an owner-less (NULL) pre-auth row. The old guard had an
            # `existing["user_id"] and` short-circuit that SKIPPED the check for
            # NULL-owner rows, letting any logged-in user overwrite/wipe an orphan
            # project by id. (Orphans are reassigned to the bootstrap admin by
            # _backfill_orphan_project_owners at startup.) user_id is None only in
            # SAMATU_AUTH_DISABLED single-tenant mode, where ownership doesn't apply.
            if user_id and existing["user_id"] != user_id:
                raise PermissionError(f"User {user_id} does not own project {project_id}")
            created_at = existing["created_at"]
            owner = existing["user_id"] or user_id
        else:
            created_at = payload.get("created_date") or now
            owner = user_id

        c.execute("""
            INSERT INTO projects
                (id, user_id, name, company_name, tipas, archetipas, status,
                 bendras_plotas_m2, vat_rate, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                company_name=excluded.company_name,
                tipas=excluded.tipas,
                archetipas=excluded.archetipas,
                status=excluded.status,
                bendras_plotas_m2=excluded.bendras_plotas_m2,
                vat_rate=excluded.vat_rate,
                data=excluded.data,
                updated_at=excluded.updated_at
        """, (
            project_id, owner, name,
            payload.get("company_name"), tipas, payload.get("archetipas"),
            payload.get("status", "ready"),
            payload.get("bendras_plotas_m2"), payload.get("vat_rate", 21),
            blob, created_at, now,
        ))
    return get_project(project_id) or {}


def delete_project(project_id: str, user_id: str | None = None) -> bool:
    """Delete project. If user_id given — enforce ownership."""
    with _conn() as c:
        if user_id:
            cursor = c.execute("DELETE FROM projects WHERE id = ? AND user_id = ?",
                               (project_id, user_id))
        else:
            cursor = c.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return cursor.rowcount > 0


# ── Extractions ───────────────────────────────────────────────────────────────

def save_extraction(project_id: str, extraction_id: str, response: dict,
                     pdf_sha256: str = "", pdf_size: int = 0,
                     page_count: int = 0) -> None:
    """Archive a Vision extraction response for cost analysis + audit."""
    # Sprint §AUDIT (2026-04-29): use shared pricing module (was duplicate
    # constants in both backend and frontend). 2026-07-04: calc_meta_cost_usd
    # is voting_models-aware — mixed-model voting rounds are priced per-round
    # at each round's model rates; single-model metas price identically to
    # the old inline call.
    from pricing import calc_meta_cost_usd
    meta = response.get("_meta") or {}
    model = meta.get("model") or "claude-opus-4-8"
    cost_usd = calc_meta_cost_usd(meta, default_model="claude-opus-4-8")
    cost_eur = cost_usd * 0.93  # rough USD→EUR
    with _conn() as c:
        c.execute("""
            INSERT INTO extractions
                (id, project_id, pdf_sha256, pdf_size_bytes, pdf_page_count,
                 raw_response, input_tokens, output_tokens, cache_read_tokens,
                 elapsed_s, cost_eur, model, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            extraction_id, project_id, pdf_sha256, pdf_size, page_count,
            json.dumps(response, ensure_ascii=False),
            int(meta.get("input_tokens") or 0),
            int(meta.get("output_tokens") or 0),
            int(meta.get("cache_read_tokens") or 0),
            meta.get("elapsed_s") or response.get("_elapsed_s"),
            round(cost_eur, 4),
            model,
            _now_iso(),
        ))


def list_extractions(project_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT id, pdf_sha256, pdf_size_bytes, pdf_page_count,
                   input_tokens, output_tokens, cache_read_tokens,
                   elapsed_s, cost_eur, model, extracted_at
              FROM extractions
             WHERE project_id = ?
          ORDER BY extracted_at DESC
        """, (project_id,)).fetchall()
        return [dict(r) for r in rows]


def user_recent_spend_eur(user_id: str, hours: int = 24) -> tuple[float, int]:
    """Sum cost_eur of extractions for a user's projects within the last N hours.
    Returns (total_eur, extraction_count). Used by per-user spend cap (M5)."""
    if not user_id:
        return (0.0, 0)
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with _conn() as c:
        row = c.execute("""
            SELECT COALESCE(SUM(e.cost_eur), 0) AS total_eur,
                   COUNT(e.id) AS n
              FROM extractions e
              JOIN projects p ON p.id = e.project_id
             WHERE p.user_id = ?
               AND e.extracted_at >= ?
        """, (user_id, cutoff)).fetchone()
        return (float(row["total_eur"] or 0), int(row["n"] or 0))


def record_usage(user_id: str | None, response: dict | None,
                 kind: str = "extract") -> float:
    """Record one Vision call's cost in the user-keyed usage_events ledger.
    Returns the recorded cost in EUR (0.0 if nothing recorded). Best-effort —
    callers wrap in try/except so metering never breaks an extraction.

    This is what makes the per-user spend cap actually fire: ``save_extraction``
    can't run at extract time (no project row yet), so cost is metered here
    against the user instead. (2026-06-19 commercial level-up.)"""
    if not user_id:
        return 0.0
    from pricing import calc_meta_cost_usd
    import uuid as _uuid
    meta = (response or {}).get("_meta") or {}
    in_t = int(meta.get("input_tokens") or 0)
    out_t = int(meta.get("output_tokens") or 0)
    cache_t = int(meta.get("cache_read_tokens") or 0)
    cache_w = int(meta.get("cache_write_tokens") or 0)
    model = meta.get("model") or "claude-opus-4-8"
    if in_t == 0 and out_t == 0 and cache_t == 0 and cache_w == 0:
        return 0.0  # nothing billable to record
    # 2026-07-04: voting_models-aware — mixed-model rounds priced per-round
    # at each round's model rates; identical result when the key is absent.
    cost_eur = calc_meta_cost_usd(meta, default_model="claude-opus-4-8") * 0.93
    with _conn() as c:
        c.execute("""
            INSERT INTO usage_events
                (id, user_id, kind, input_tokens, output_tokens,
                 cache_read_tokens, cost_eur, model, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (_uuid.uuid4().hex, user_id, kind, in_t, out_t, cache_t,
              round(cost_eur, 4), model, _now_iso()))
    return cost_eur


def record_reservation(user_id: str | None, cost_eur: float, kind: str = "reserve") -> float:
    """Record a conservative pre-charge (no token data) in usage_events BEFORE a
    Claude call, so the per-user spend cap counts EVERY billable endpoint — not
    just extract-interior — and concurrent requests can't outrun it (the original
    TOCTOU race). Best-effort; callers wrap in try/except. (2026-06-19 bug-hunt.)"""
    if not user_id or cost_eur <= 0:
        return 0.0
    import uuid as _uuid
    with _conn() as c:
        c.execute("""
            INSERT INTO usage_events
                (id, user_id, kind, input_tokens, output_tokens,
                 cache_read_tokens, cost_eur, created_at)
            VALUES (?, ?, ?, 0, 0, 0, ?, ?)
        """, (_uuid.uuid4().hex, user_id, kind, round(float(cost_eur), 4), _now_iso()))
    return cost_eur


def user_usage_since(user_id: str, hours: int = 24,
                     kind_like: str | None = None) -> tuple[float, int]:
    """Sum cost_eur + count of usage_events for a user within the last N hours.
    Returns (total_eur, event_count). Source of truth for the per-user spend cap.

    `kind_like`: when set, the COUNT (n) includes ONLY events whose kind matches
    this SQL LIKE pattern (the SUM always reflects every event). Used so the
    hourly-EXTRACT cap counts only extraction events ('%extract%' — extract-interior
    actuals + reserve:/extract* pre-charges) and is not tripped by light-endpoint
    reservations (chat/vision_fill/lasso/symbols). (2026-06-19.)"""
    if not user_id:
        return (0.0, 0)
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with _conn() as c:
        if kind_like:
            row = c.execute("""
                SELECT COALESCE(SUM(cost_eur), 0) AS total_eur,
                       COALESCE(SUM(CASE WHEN kind LIKE ? THEN 1 ELSE 0 END), 0) AS n
                  FROM usage_events
                 WHERE user_id = ? AND created_at >= ?
            """, (kind_like, user_id, cutoff)).fetchone()
        else:
            row = c.execute("""
                SELECT COALESCE(SUM(cost_eur), 0) AS total_eur, COUNT(id) AS n
                  FROM usage_events
                 WHERE user_id = ? AND created_at >= ?
            """, (user_id, cutoff)).fetchone()
        return (float(row["total_eur"] or 0), int(row["n"] or 0))


# ── Corrections (audit log for future learning-loop) ──────────────────────────

def log_correction(project_id: str, field_path: str,
                    old_value: Any, new_value: Any,
                    source: str = "inline_edit",
                    room_nr: str | None = None,
                    note: str | None = None) -> None:
    """Track every user-driven change for later prompt iteration."""
    with _conn() as c:
        c.execute("""
            INSERT INTO corrections
                (project_id, room_nr, field_path, old_value, new_value,
                 source, note, occurred_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id, room_nr, field_path,
            json.dumps(old_value, ensure_ascii=False) if old_value is not None else None,
            json.dumps(new_value, ensure_ascii=False) if new_value is not None else None,
            source, note, _now_iso(),
        ))


def list_corrections(project_id: str | None = None, limit: int = 500) -> list[dict]:
    """All corrections for a project, or globally if project_id is None."""
    with _conn() as c:
        if project_id:
            rows = c.execute("""
                SELECT * FROM corrections
                 WHERE project_id = ?
              ORDER BY occurred_at DESC LIMIT ?
            """, (project_id, limit)).fetchall()
        else:
            rows = c.execute("""
                SELECT * FROM corrections
              ORDER BY occurred_at DESC LIMIT ?
            """, (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("old_value", "new_value"):
                if d.get(k):
                    try:
                        d[k] = json.loads(d[k])
                    except Exception:
                        pass
            out.append(d)
        return out


def corrections_summary() -> list[dict]:
    """Aggregated correction patterns — how often each field is overridden.
    Used by admin dashboard / manual prompt iteration to identify systemic
    Vision biases (eg. 'users override drabuzine_painted=false 70% of time')."""
    with _conn() as c:
        rows = c.execute("""
            SELECT field_path,
                   COUNT(*) as count,
                   COUNT(DISTINCT project_id) as projects,
                   MAX(occurred_at) as last_seen
              FROM corrections
          GROUP BY field_path
          ORDER BY count DESC
        """).fetchall()
        return [dict(r) for r in rows]


def _migrate_schema() -> None:
    """Idempotent column additions for existing DBs created before auth.
    SQLite ALTER TABLE only supports ADD COLUMN — keep migrations append-only."""
    with _conn() as c:
        cols = {row["name"] for row in c.execute("PRAGMA table_info(projects)").fetchall()}
        if cols and "user_id" not in cols:
            c.execute("ALTER TABLE projects ADD COLUMN user_id TEXT")
            c.execute("CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id)")
        # SM04 — read-only share link
        if cols and "share_token" not in cols:
            c.execute("ALTER TABLE projects ADD COLUMN share_token TEXT")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_share ON projects(share_token) WHERE share_token IS NOT NULL")
        # Sprint §36 (2026-04-29): share token expiry + view tracking
        if cols and "share_expires_at" not in cols:
            c.execute("ALTER TABLE projects ADD COLUMN share_expires_at TEXT")
        if cols and "share_view_count" not in cols:
            c.execute("ALTER TABLE projects ADD COLUMN share_view_count INTEGER DEFAULT 0")
        if cols and "share_last_viewed_at" not in cols:
            c.execute("ALTER TABLE projects ADD COLUMN share_last_viewed_at TEXT")
        # M4 (2026-05-06): Google OAuth users — google_sub stable subject ID,
        # avatar URL, and password_hash NULL allowed (OAuth-only users have
        # no password).
        ucols = {row["name"] for row in c.execute("PRAGMA table_info(users)").fetchall()}
        if ucols and "google_sub" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN google_sub TEXT")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub) WHERE google_sub IS NOT NULL")
        if ucols and "avatar_url" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
        # W1.1 (2026-07-03): model-aware telemetry — which Claude model
        # produced each extraction / usage event (Opus 4.8 vs Fable 5 bench).
        ecols = {row["name"] for row in c.execute("PRAGMA table_info(extractions)").fetchall()}
        if ecols and "model" not in ecols:
            c.execute("ALTER TABLE extractions ADD COLUMN model TEXT")
        uecols = {row["name"] for row in c.execute("PRAGMA table_info(usage_events)").fetchall()}
        if uecols and "model" not in uecols:
            c.execute("ALTER TABLE usage_events ADD COLUMN model TEXT")
        # F2 (2026-07-04 pentest): session-version nonce for logout /
        # change-password invalidation. Every session cookie stores the value it
        # was minted against; require_user rejects when it no longer matches, so
        # a captured pre-logout cookie stops replaying. SQLite ADD COLUMN can't
        # carry a non-constant default, but the literal 1 is fine and existing
        # rows backfill to 1.
        if ucols and "session_version" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1")


# ── SM04 share-link helpers ──────────────────────────────────────────────────

def set_share_token(project_id: str, token: str, expires_at: str | None = None) -> None:
    """Sprint §36 (2026-04-29): expires_at ISO string optional. None = no expiry.
    Resets share_view_count to 0 when issuing a fresh token."""
    with _conn() as c:
        c.execute(
            "UPDATE projects SET share_token = ?, share_expires_at = ?, "
            "share_view_count = 0, share_last_viewed_at = NULL, updated_at = ? WHERE id = ?",
            (token, expires_at, _now_iso(), project_id),
        )


def clear_share_token(project_id: str) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE projects SET share_token = NULL, share_expires_at = NULL, "
            "share_view_count = 0, share_last_viewed_at = NULL, updated_at = ? WHERE id = ?",
            (_now_iso(), project_id),
        )


def get_share_status(project_id: str) -> dict | None:
    """Return current share token state for owner UI."""
    with _conn() as c:
        row = c.execute(
            "SELECT share_token, share_expires_at, share_view_count, share_last_viewed_at "
            "FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "token": row["share_token"],
            "expires_at": row["share_expires_at"],
            "view_count": row["share_view_count"] or 0,
            "last_viewed_at": row["share_last_viewed_at"],
        }


def increment_share_view(token: str) -> None:
    """Atomically bump view_count + last_viewed_at when share URL accessed."""
    if not token:
        return
    with _conn() as c:
        c.execute(
            "UPDATE projects SET share_view_count = COALESCE(share_view_count, 0) + 1, "
            "share_last_viewed_at = ? WHERE share_token = ?",
            (_now_iso(), token),
        )


def get_project_by_share_token(token: str) -> dict | None:
    """Sprint §36: now also checks expires_at — returns None if expired."""
    if not token:
        return None
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM projects WHERE share_token = ?", (token,)
        ).fetchone()
        if not row:
            return None
        # Check expiry
        expires = row["share_expires_at"] if "share_expires_at" in row.keys() else None
        if expires:
            try:
                from datetime import datetime
                exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00") if expires.endswith("Z") else expires)
                if exp_dt < datetime.now(exp_dt.tzinfo):
                    return None  # expired
            except (ValueError, TypeError):
                pass  # malformed expiry — treat as non-expiring
        d = dict(row)
        # Inflate data JSON blob
        try:
            d["data"] = json.loads(d.get("data") or "{}")
        except json.JSONDecodeError:
            d["data"] = {}
        return d


def _backfill_orphan_project_owners() -> int:
    """Assign owner-less (NULL user_id) projects — left over from the pre-auth
    single-tenant era — to the bootstrap admin (the first registered admin), so
    no orphan rows remain for the upsert ownership barrier to have to fend off.
    Returns the number of rows reassigned. Best-effort; never blocks startup.
    (2026-06-19 security hunt.)"""
    try:
        with _conn() as c:
            n_orphans = c.execute(
                "SELECT COUNT(*) AS n FROM projects WHERE user_id IS NULL"
            ).fetchone()["n"]
            if not n_orphans:
                return 0
            admin = c.execute(
                "SELECT id FROM users WHERE is_admin = 1 ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if not admin:
                return 0  # no admin yet → leave orphans inert (unreadable/unwritable)
            c.execute(
                "UPDATE projects SET user_id = ? WHERE user_id IS NULL", (admin["id"],)
            )
            return n_orphans
    except Exception:
        return 0


# Initialize schema on module import
init_schema()
_migrate_schema()
_backfill_orphan_project_owners()
