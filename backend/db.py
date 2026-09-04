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
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

log = logging.getLogger("pathon.db")

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
                id                 TEXT PRIMARY KEY,
                user_id            TEXT NOT NULL,
                kind               TEXT,
                input_tokens       INTEGER,
                output_tokens      INTEGER,
                cache_read_tokens  INTEGER,
                -- T2 (2026-07-28 telemetry audit): cache WRITES were priced into
                -- cost_eur but stored nowhere, so a cache regression (breakpoint
                -- moved, prefix invalidated, TTL expiring between voting rounds)
                -- was invisible — the bill rose with no column to explain it.
                cache_write_tokens INTEGER,
                -- The extra_calls (sub-Vision) share of cost_eur. 65-74% of a
                -- typical extraction's cost lives here and was unattributable.
                extra_calls_cost_eur REAL,
                cost_eur           REAL,
                model              TEXT,               -- W1.1 (2026-07-03)
                created_at         TEXT NOT NULL
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


def set_stripe_customer_id(user_id: str, customer_id: str) -> None:
    """Persist the user's Stripe Customer id on their row (create-or-reuse).

    W3 billing: written once, on first Checkout, then reused so a user maps to a
    single Stripe customer across subscriptions and one-off purchases."""
    with _conn() as c:
        c.execute("UPDATE users SET stripe_customer_id = ? WHERE id = ?",
                  (customer_id, user_id))


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
        raw = d.pop("data", None)
        try:
            data = json.loads(raw or "{}")
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            # A corrupt/truncated data blob must NOT silently return an empty
            # project — that reads as success while the user's rooms, pozicijos
            # and corrections vanish with no trace. Log loudly (so ops can
            # restore from the R2 DB backup) and return a corruption MARKER so
            # the caller can tell "corrupt" apart from "genuinely empty".
            # (audit 2026-07-06: previously `except Exception: data = {}`.)
            log.error("project %s has a corrupt/undecodable data blob (%s); "
                      "returning a corruption marker, NOT a silent empty project",
                      project_id, exc)
            data = {"_data_corrupt": True, "_raw_len": len(raw or "")}
        return {**data, **{k: v for k, v in d.items() if v is not None}}


def project_exists(project_id: str, user_id: str | None = None) -> bool:
    """Cheap existence + ownership check — no data blob read.

    get_project() pulls and json.loads()es the whole ~175 KB blob; callers that
    only need "does this exist and is it mine?" (the PDF stream endpoint) paid
    that for nothing. SELECT 1 with the same ownership semantics.
    """
    with _conn() as c:
        if user_id:
            row = c.execute("SELECT 1 FROM projects WHERE id = ? AND user_id = ?",
                            (project_id, user_id)).fetchone()
        else:
            row = c.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone()
        return row is not None


class ProjectConflictError(Exception):
    """Raised by upsert_project when base_updated_at does not match the row.

    Carries the CURRENT server timestamp so the caller can tell the client what
    it is now out of date against.
    """

    def __init__(self, project_id: str, current_updated_at: str | None):
        super().__init__(
            f"Project {project_id} was modified since base_updated_at="
            f"{current_updated_at!r}"
        )
        self.project_id = project_id
        self.current_updated_at = current_updated_at


def upsert_project(project_id: str, payload: dict, user_id: str | None = None,
                   base_updated_at: str | None = None) -> dict:
    """Insert or full-replace. user_id stored on create; on update, ownership
    is checked first (raises if mismatch).

    `base_updated_at` (optional) is the updated_at the client last SAW. When
    given and the stored row has moved on, raise ProjectConflictError instead of
    silently destroying the other writer's changes (two tabs on one project used
    to lose whichever save landed first, with no warning). Omitted → the check
    is skipped entirely, so legacy clients, scripts and restore flows behave
    exactly as before. The comparison happens INSIDE the _conn() block, which
    holds the global _DB_LOCK, so check-and-write is atomic.
    """
    now = _now_iso()
    name = payload.get("name") or "Naujas projektas"
    tipas = payload.get("tipas") or "interjeras"
    blob = json.dumps(payload, ensure_ascii=False)
    with _conn() as c:
        existing = c.execute(
            "SELECT created_at, user_id, updated_at FROM projects WHERE id = ?",
            (project_id,),
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
            # Lost-update detection (2026-07-28 sweep). Ownership is checked
            # first on purpose: a cross-user write is a 403, not a 409.
            if base_updated_at is not None and existing["updated_at"] != base_updated_at:
                raise ProjectConflictError(project_id, existing["updated_at"])
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
    from pricing import calc_meta_cost_usd, calc_extra_calls_cost_usd, USD_TO_EUR
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
    # T2 (2026-07-28): the sub-Vision (extra_calls) share of that same total —
    # the dominant, previously unattributable slice. Priced by the SAME helper
    # calc_meta_cost_usd uses internally, so it is always <= cost_eur and never
    # a second, independently-drifting estimate. Best-effort: an unpriceable
    # entry must not lose the whole usage_event.
    try:
        extra_eur = calc_extra_calls_cost_usd(meta) * USD_TO_EUR
    except Exception as exc:
        print(f"[usage] extra_calls pricing failed ({exc}) — storing NULL")
        extra_eur = None
    with _conn() as c:
        c.execute("""
            INSERT INTO usage_events
                (id, user_id, kind, input_tokens, output_tokens,
                 cache_read_tokens, cache_write_tokens, extra_calls_cost_eur,
                 cost_eur, model, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (_uuid.uuid4().hex, user_id, kind, in_t, out_t, cache_t, cache_w,
              None if extra_eur is None else round(extra_eur, 4),
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


# ── W3 billing usage ledger (project-count quota) ─────────────────────────────
#
# Separate from usage_events (the € cost ledger / spend cap): billing_usage
# counts *projects* consumed against a plan's monthly quota. One row per
# successful billable extraction. Written only when BILLING_ENABLED (the
# caller guards on the flag); read by billing/entitlements.py.

def record_billing_usage(user_id: str, kind: str = "extract",
                         project_id: str | None = None) -> None:
    """Append one billable-usage row (one successful project analysis).
    Caller guards on billing_enabled(); this is a plain durable insert."""
    if not user_id:
        return
    with _conn() as c:
        c.execute(
            "INSERT INTO billing_usage (user_id, kind, project_id, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, kind, project_id, _now_iso()),
        )


def billing_usage_in_period(user_id: str, current_period_end: str | None = None,
                            kind: str = "extract") -> int:
    """Count billing_usage rows of `kind` for a user within the current billing
    period. Subscriber (current_period_end set): window is
    [current_period_end − ~30 days, current_period_end). Otherwise: calendar
    month (first-of-this-month → now). Returns 0 for an unknown/empty user."""
    if not user_id:
        return 0
    from datetime import datetime, timedelta, timezone
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    window_start: str
    window_end: str | None = None
    if current_period_end:
        try:
            # current_period_end may carry a trailing 'Z'; strip it before parse.
            pe = datetime.strptime(current_period_end.replace("Z", ""),
                                   "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            window_start = (pe - timedelta(days=30)).strftime(fmt)
            window_end = pe.strftime(fmt)
        except ValueError:
            # Malformed period end → fall back to calendar month.
            current_period_end = None
    if not current_period_end:
        now = datetime.now(timezone.utc)
        window_start = now.replace(day=1, hour=0, minute=0, second=0,
                                   microsecond=0).strftime(fmt)
    with _conn() as c:
        if window_end is not None:
            row = c.execute(
                "SELECT COUNT(*) AS n FROM billing_usage "
                "WHERE user_id = ? AND kind = ? "
                "AND created_at >= ? AND created_at < ?",
                (user_id, kind, window_start, window_end),
            ).fetchone()
        else:
            row = c.execute(
                "SELECT COUNT(*) AS n FROM billing_usage "
                "WHERE user_id = ? AND kind = ? AND created_at >= ?",
                (user_id, kind, window_start),
            ).fetchone()
        return int(row["n"] or 0)


def rolled_over_credits(user_id: str) -> int:
    """Unused quota carried from prior periods. Returns 0 until a rollover
    QUOTA_POLICY is chosen (YAGNI — the founder deferred the rollover
    decision). Only read by entitlements when QUOTA_POLICY != 'expire'."""
    return 0


# ── One-off credits (non-expiring, ledger-backed) ─────────────────────────────
#
# A one-off purchase (€12) is a CREDIT, not a plan state — a user is never set to
# plan="oneoff". Credits live in the same billing_usage table as extract usage,
# distinguished by kind, so no new table is needed:
#   kind="credit_granted"  = +1 credit (grant_oneoff_credit; the Phase-3 webhook
#                            calls this on a successful one-off Checkout)
#   kind="credit_consumed" = -1 credit (main.py draws one after the monthly slot)
# Balance = count(granted) - count(consumed). LIFETIME — never period-scoped, so
# credits do not expire when a billing period rolls over.

def grant_oneoff_credit(user_id: str) -> None:
    """Grant one non-expiring project credit (one-off purchase). Idempotency is
    the caller's concern (the webhook keys on the Stripe event id)."""
    record_billing_usage(user_id, kind="credit_granted", project_id=None)


def credits_balance(user_id: str) -> int:
    """Lifetime one-off credit balance = granted − consumed (never < 0 in
    practice; consumption is gated on a positive balance). 0 for empty user."""
    if not user_id:
        return 0
    with _conn() as c:
        row = c.execute(
            "SELECT "
            "SUM(CASE WHEN kind = 'credit_granted' THEN 1 "
            "         WHEN kind = 'credit_consumed' THEN -1 ELSE 0 END) AS bal "
            "FROM billing_usage WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return int(row["bal"] or 0)


def _consume_oneoff_credit_if_available(user_id: str) -> bool:
    """Atomically consume one one-off credit iff the balance is > 0. Returns True
    if a credit was consumed.

    This is a SINGLE conditional INSERT ... SELECT so the balance-check and the
    consume are one atomic statement — closing the check-then-act race where two
    concurrent extractions both read balance==1 and both write credit_consumed,
    driving the balance to −1 (one free extraction). The WHERE subquery re-reads
    the ledger balance inside the same statement; SQLite serializes writers, so
    the second caller sees balance==0 and inserts nothing. (audit 2026-07-06)"""
    if not user_id:
        return False
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO billing_usage (user_id, kind, project_id, created_at) "
            "SELECT ?, 'credit_consumed', NULL, ? "
            "WHERE (SELECT COALESCE(SUM(CASE WHEN kind = 'credit_granted' THEN 1 "
            "                                WHEN kind = 'credit_consumed' THEN -1 "
            "                                ELSE 0 END), 0) "
            "       FROM billing_usage WHERE user_id = ?) > 0",
            (user_id, _now_iso(), user_id),
        )
        return cur.rowcount > 0


def record_extract_and_maybe_consume_credit(user_id: str) -> None:
    """Record one successful billable extraction, drawing monthly-slot-first,
    then a one-off credit.

    Always writes kind="extract" (the per-project audit / period counter). If
    this extraction is beyond the plan's monthly quota AND the user has a credit
    to spend, ALSO writes kind="credit_consumed" (−1). Balance never goes
    negative — the credit_consumed is written atomically only when balance > 0.

    Caller guards on billing_enabled(); this is plain bookkeeping (the caller
    wraps it so a failure here never breaks extraction)."""
    if not user_id:
        return
    from billing.plans import PLAN_BY_ID
    user = get_user_by_id(user_id)
    plan_id = (user or {}).get("plan") or "free"
    plan = PLAN_BY_ID.get(plan_id, PLAN_BY_ID["free"])
    period_end = (user or {}).get("current_period_end")
    # used_before: extractions already spent THIS period, computed before we
    # record the current one.
    used_before = billing_usage_in_period(
        user_id, current_period_end=period_end, kind="extract")
    record_billing_usage(user_id, kind="extract", project_id=None)
    # Beyond the monthly allotment → draw a credit if one remains (atomic).
    if used_before >= int(plan.get("monthly_quota", 0)):
        _consume_oneoff_credit_if_available(user_id)


# ── Free-trial anti-abuse (company-code gated, survives account deletion) ─────
#
# consumed_trials is keyed by the NORMALIZED company code and is NOT
# FK-referenced to users — deleting a user leaves the row, so a re-registered
# account with the same įmonės kodas cannot reclaim the one free trial. See
# backend/billing/trial.py for the normalization + gate.

def trial_consumed(company_code: str) -> bool:
    """True iff this (already-normalized) company code is in consumed_trials.
    Empty code → False (never claimed)."""
    if not company_code:
        return False
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM consumed_trials WHERE company_code = ?",
            (company_code,),
        ).fetchone()
        return row is not None


def consume_trial(company_code: str, user_id: str | None) -> bool:
    """Insert the (already-normalized) company code into consumed_trials
    (UNIQUE). Returns True on a fresh consume, False if this company already
    consumed its trial (IntegrityError on the UNIQUE column) or the code is
    empty. The UNIQUE constraint makes this the atomic one-per-company gate."""
    if not company_code:
        return False
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO consumed_trials (company_code, user_id, consumed_at) "
                "VALUES (?, ?, ?)",
                (company_code, user_id, _now_iso()),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def set_user_company(user_id: str, company_code: str,
                     pvm_code: str | None = None) -> None:
    """Persist the user's company_code (+ optional PVM kodas) on their row.
    Caller validates/normalizes via billing.trial.normalize_company_code before
    calling. No-op for an empty user_id."""
    if not user_id:
        return
    with _conn() as c:
        c.execute(
            "UPDATE users SET company_code = ?, "
            "pvm_code = COALESCE(?, pvm_code) WHERE id = ?",
            (company_code, pvm_code, user_id),
        )


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


# ── Price lists / kainynai (2026-09-02) ───────────────────────────────────────
#
# The contractor's own €/vnt list. Until now these lived ONLY in localStorage
# (projectStore `samatu_price_lists`), so a cleared browser or a second device
# lost the one artefact the user had typed by hand. This table is the source of
# truth; the frontend store keeps a write-through cache in front of it.
#
# `items` is the same JSON array the CSV/xlsx importers produce:
#   [{skyrius, aprasymas, mato_vnt, kaina}, …]
# stored verbatim so importer and matcher stay the only owners of that shape.
#
# Ownership follows projects EXACTLY, including the NULL-owner write barrier
# (2026-06-19 hunt): an authenticated caller may never write a row owned by
# someone else, an owner-less row included.
#
# 2026-09-02 review: `user_id` is REQUIRED on every function below and there is
# no unscoped branch left. Two reasons. `if user_id:` is truthiness, so an empty
# string — a plausible shape for a mis-wired caller — took the UNSCOPED path and
# `list_price_lists("")` handed back every user's kainynai. And nothing outside
# the tests ever wanted the unscoped read: the router always has a session. An
# owner-less row can therefore no longer be CREATED either; the ones that exist
# are legacy, and the write barrier below still refuses to hand them to anyone.

def _require_user_id(user_id: str) -> str:
    """Refuse a missing/empty owner loudly instead of widening the query."""
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("price list access requires a non-empty user_id")
    return user_id


def list_price_lists(user_id: str) -> list[dict]:
    """All of one user's price lists, newest first."""
    _require_user_id(user_id)
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM price_lists WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [_price_list_row_to_dict(r) for r in rows]


def _price_list_row_to_dict(row) -> dict:
    d = dict(row)
    raw = d.pop("items", None)
    try:
        items = json.loads(raw or "[]")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        # Same reasoning as get_project: a corrupt blob must not read as an
        # EMPTY price list — that silently un-prices every future sąmata.
        log.error("price list %s has a corrupt items blob (%s)", d.get("id"), exc)
        items = []
        d["_items_corrupt"] = True
    d["items"] = items if isinstance(items, list) else []
    d["total_items"] = len(d["items"])
    d["is_default"] = bool(d.get("is_default"))
    # The frontend cache has always called this field `created_date`.
    d["created_date"] = d.get("created_at")
    return d


def get_price_list(price_list_id: str, user_id: str) -> dict | None:
    _require_user_id(user_id)
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM price_lists WHERE id = ? AND user_id = ?",
            (price_list_id, user_id)).fetchone()
        return _price_list_row_to_dict(row) if row else None


def _read_price_list(c, price_list_id: str) -> dict | None:
    """Owner-agnostic read on an OPEN connection. Private on purpose: the only
    caller is `upsert_price_list`, reading back the row it just wrote inside the
    same transaction (which also closes the read-after-write window a second
    connection would have opened)."""
    row = c.execute("SELECT * FROM price_lists WHERE id = ?",
                    (price_list_id,)).fetchone()
    return _price_list_row_to_dict(row) if row else None


def upsert_price_list(price_list_id: str, payload: dict,
                      user_id: str) -> dict:
    """Insert or full-replace one price list.

    `is_default` is exclusive per user: setting it here clears the flag on that
    user's other lists inside the SAME connection (which holds the global
    _DB_LOCK), so two concurrent "make this the default" clicks can never leave
    two defaults behind.
    """
    _require_user_id(user_id)
    now = _now_iso()
    name = (payload.get("name") or "Kainynas").strip()[:200]
    items = payload.get("items")
    if not isinstance(items, list):
        items = []
    blob = json.dumps(items, ensure_ascii=False)
    is_default = 1 if payload.get("is_default") else 0
    with _conn() as c:
        existing = c.execute(
            "SELECT created_at, user_id FROM price_lists WHERE id = ?",
            (price_list_id,)).fetchone()
        if existing:
            # No `user_id and …` guard: an empty owner used to skip the barrier
            # entirely. A legacy NULL-owner row still fails this comparison, so
            # it stays unwritable — the 2026-06-19 write-barrier lesson.
            if existing["user_id"] != user_id:
                raise PermissionError(
                    f"User {user_id} does not own price list {price_list_id}")
            created_at = existing["created_at"]
            owner = existing["user_id"]
        else:
            created_at = payload.get("created_date") or payload.get("created_at") or now
            owner = user_id
        c.execute("""
            INSERT INTO price_lists
                (id, user_id, name, company_name, items, is_default,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                company_name=excluded.company_name,
                items=excluded.items,
                is_default=excluded.is_default,
                updated_at=excluded.updated_at
        """, (price_list_id, owner, name, payload.get("company_name"),
              blob, is_default, created_at, now))
        if is_default and owner:
            c.execute(
                "UPDATE price_lists SET is_default = 0, updated_at = ? "
                " WHERE user_id = ? AND id != ?", (now, owner, price_list_id))
        return _read_price_list(c, price_list_id) or {}


def delete_price_list(price_list_id: str, user_id: str) -> bool:
    _require_user_id(user_id)
    with _conn() as c:
        cur = c.execute("DELETE FROM price_lists WHERE id = ? AND user_id = ?",
                        (price_list_id, user_id))
        return cur.rowcount > 0


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
        # T2 (2026-07-28 telemetry audit): cache-write volume + the extra_calls
        # share of cost_eur. Both NULL on pre-migration rows — that is the honest
        # value (we never captured them), NOT zero, so readers must treat NULL as
        # "unknown" rather than "no cache writes happened".
        if uecols and "cache_write_tokens" not in uecols:
            c.execute("ALTER TABLE usage_events ADD COLUMN cache_write_tokens INTEGER")
        if uecols and "extra_calls_cost_eur" not in uecols:
            c.execute("ALTER TABLE usage_events ADD COLUMN extra_calls_cost_eur REAL")
        # F2 (2026-07-04 pentest): session-version nonce for logout /
        # change-password invalidation. Every session cookie stores the value it
        # was minted against; require_user rejects when it no longer matches, so
        # a captured pre-logout cookie stops replaying. SQLite ADD COLUMN can't
        # carry a non-constant default, but the literal 1 is fine and existing
        # rows backfill to 1.
        if ucols and "session_version" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1")
        # W3 (2026-07-04): billing subsystem — plan state lives on the users
        # row (Stripe is the source of truth, mirrored locally via webhooks).
        # Dormant: BILLING_ENABLED defaults OFF (backend/billing/flag.py), so
        # these columns/tables exist but are unread on the hot path until the
        # flag flips. Append-only, mirrors the google_sub/session_version
        # pattern above.
        if "plan" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'")
        if "plan_status" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN plan_status TEXT NOT NULL DEFAULT 'active'")
        for col in ("stripe_customer_id", "stripe_subscription_id",
                    "current_period_end", "company_code", "pvm_code"):
            if col not in ucols:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
        # consumed_trials: keyed by company code, SURVIVES user deletion —
        # anti-abuse gate for the 1-project free trial.
        c.execute("""
            CREATE TABLE IF NOT EXISTS consumed_trials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_code TEXT NOT NULL UNIQUE,
                user_id TEXT,
                consumed_at TEXT NOT NULL
            )""")
        # billing_usage: per-billable-extraction ledger, keyed to billing period.
        c.execute("""
            CREATE TABLE IF NOT EXISTS billing_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                project_id TEXT,
                created_at TEXT NOT NULL
            )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_billing_usage_user_time ON billing_usage(user_id, created_at)")
        # webhook_events: Stripe delivery de-dup. event_id is the PRIMARY KEY, so
        # a re-delivered event fails the INSERT (IntegrityError) — seen_webhook
        # turns that into an atomic "already processed" signal, guaranteeing each
        # event's effect (credit grant, plan mutation) is applied exactly once.
        c.execute("""
            CREATE TABLE IF NOT EXISTS webhook_events (
                event_id    TEXT PRIMARY KEY,
                received_at TEXT NOT NULL
            )""")
        # invoices: one row per emitted PVM sąskaita-faktūra (Task 14). The PDF
        # bytes live in object storage (invoices/<id>.pdf); this row is the
        # owner-scoped index + numbering ledger. user_id is NOT NULL so every
        # invoice has an owner (drives the IDOR-safe get_invoice accessor).
        c.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                number      TEXT,
                vat_mode    TEXT,
                total_eur   REAL,
                pdf_path    TEXT,
                created_at  TEXT NOT NULL
            )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_invoices_user_time ON invoices(user_id, created_at)")
        # admin_audit_log (2026-07-06 audit): accountability for state-changing
        # admin operations. Append-only ledger — who (actor_user_id) did what
        # (action) to whom (target_user_id), when (created_at), plus an optional
        # human-readable detail (e.g. the target's email, preserved even if that
        # user is later deleted). Before this, disable/enable discarded the
        # calling admin's identity entirely; harmless with one admin, but a
        # second admin makes incident investigation impossible without it.
        # target_user_id/detail are nullable (an action need not target a user).
        c.execute("""
            CREATE TABLE IF NOT EXISTS admin_audit_log (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id  TEXT NOT NULL,
                action         TEXT NOT NULL,
                target_user_id TEXT,
                detail         TEXT,
                created_at     TEXT NOT NULL
            )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_admin_audit_created ON admin_audit_log(created_at DESC)")
        # price_lists (2026-09-02): the contractor's kainynas, previously
        # localStorage-only. user_id is nullable for the same reason projects'
        # is — SAMATU_AUTH_DISABLED single-tenant mode has no owner — and the
        # upsert enforces the NULL-owner write barrier either way.
        c.execute("""
            CREATE TABLE IF NOT EXISTS price_lists (
                id           TEXT PRIMARY KEY,
                user_id      TEXT,
                name         TEXT NOT NULL,
                company_name TEXT,
                items        TEXT NOT NULL,      -- JSON array
                is_default   INTEGER NOT NULL DEFAULT 0,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_price_lists_user ON price_lists(user_id, created_at DESC)")


# ── W3 billing: webhook de-dup + Stripe-state mirror helpers ─────────────────

def seen_webhook(event_id: str) -> bool:
    """Atomically record a Stripe event id and report whether it was ALREADY
    seen. Try to INSERT; on IntegrityError (the PRIMARY KEY already holds this
    id) the event is a re-delivery → return True. A fresh insert → return False
    (this caller owns applying the effect). This is the idempotency keystone: two
    concurrent deliveries race on the same INSERT and exactly one wins.

    An empty event_id is treated as "new" (returns False) so a malformed event
    still flows to the handlers, which defend themselves with .get()."""
    if not event_id:
        return False
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO webhook_events (event_id, received_at) VALUES (?, ?)",
                (event_id, _now_iso()),
            )
        return False
    except sqlite3.IntegrityError:
        return True


def forget_webhook(event_id: str) -> None:
    """Release a webhook idempotency claim recorded by seen_webhook().

    Called when the handler FAILED: the event id was already claimed (so the
    effect is NOT marked applied), and Stripe's retry should re-claim and
    re-dispatch it. Without this, a handler crash after seen_webhook() claimed
    the id would let the webhook return 200 and permanently lose the state
    update (subscription active in Stripe, free in Pathon). (audit 2026-07-06)"""
    if not event_id:
        return
    with _conn() as c:
        c.execute("DELETE FROM webhook_events WHERE event_id = ?", (event_id,))


def get_user_by_stripe_customer_id(customer_id: str) -> dict | None:
    """Resolve a user row from their Stripe Customer id. Used by subscription /
    invoice webhooks, which carry `customer` but not our internal user id.
    Returns None for an unknown / empty customer id (handler logs + skips)."""
    if not customer_id:
        return None
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM users WHERE stripe_customer_id = ?", (customer_id,)
        ).fetchone()
        return dict(row) if row else None


# Sentinel so set_user_plan can distinguish "leave stripe_subscription_id
# untouched" (default) from "explicitly clear it to NULL" (pass None).
_UNSET = object()


def set_user_plan(user_id: str, plan: str | None = None,
                  plan_status: str | None = None,
                  stripe_subscription_id: object = _UNSET,
                  current_period_end: str | None = None) -> None:
    """Mirror Stripe subscription state onto the users row. Updates ONLY the
    fields explicitly provided — a bare call is a no-op. `plan`, `plan_status`,
    and `current_period_end` are updated when non-None; `stripe_subscription_id`
    is updated whenever it is passed at all (including None, to clear it on
    cancellation) via the _UNSET sentinel. No-ops for an empty user_id."""
    if not user_id:
        return
    sets: list[str] = []
    params: list[object] = []
    if plan is not None:
        sets.append("plan = ?")
        params.append(plan)
    if plan_status is not None:
        sets.append("plan_status = ?")
        params.append(plan_status)
    if stripe_subscription_id is not _UNSET:
        sets.append("stripe_subscription_id = ?")
        params.append(stripe_subscription_id)
    if current_period_end is not None:
        sets.append("current_period_end = ?")
        params.append(current_period_end)
    if not sets:
        return
    params.append(user_id)
    with _conn() as c:
        c.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", params)


# ── W3 billing: PVM sąskaita-faktūra persistence (Task 14) ───────────────────

def next_invoice_number() -> str:
    """Sequential invoice number, `PATHON-{year}-{6-digit seq}`. seq is derived
    from the current invoice count (+1), zero-padded — simple + monotonic. Not
    strictly gap-free across years, but always increasing and human-readable.
    Called just before insert_invoice; the tiny race window (two concurrent
    emissions) is acceptable for a dormant one-emission-per-payment path and the
    `id` PK is the true uniqueness guarantee."""
    year = time.strftime("%Y", time.gmtime())
    with _conn() as c:
        row = c.execute("SELECT COUNT(*) AS n FROM invoices").fetchone()
    seq = int(row["n"] or 0) + 1
    return f"PATHON-{year}-{seq:06d}"


def insert_invoice(id: str, user_id: str, number: str, vat_mode: str,
                   total_eur: float, pdf_path: str) -> None:
    """Insert one emitted-invoice row. The PDF bytes live at `pdf_path` in object
    storage; this row is the owner-scoped index."""
    with _conn() as c:
        c.execute(
            "INSERT INTO invoices (id, user_id, number, vat_mode, total_eur, "
            "pdf_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (id, user_id, number, vat_mode, total_eur, pdf_path, _now_iso()),
        )


def get_invoice(invoice_id: str, user_id: str | None = None) -> dict | None:
    """Fetch an invoice row. When user_id is given, enforce ownership — returns
    None if the invoice is not owned by that user (the IDOR-safe accessor;
    mirrors get_project). None also for an unknown id."""
    with _conn() as c:
        if user_id:
            row = c.execute(
                "SELECT * FROM invoices WHERE id = ? AND user_id = ?",
                (invoice_id, user_id)).fetchone()
        else:
            row = c.execute(
                "SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        return dict(row) if row else None


def list_invoices(user_id: str) -> list[dict]:
    """All invoices owned by user_id, newest first. Never leaks another user's
    rows (parameterized on user_id). Empty list for an unknown user."""
    if not user_id:
        return []
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM invoices WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)).fetchall()
        return [dict(r) for r in rows]


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
            except (ValueError, TypeError, AttributeError):
                # 2026-07-27 audit (finding 9): a malformed expiry used to FAIL
                # OPEN — the share link kept working forever. An unreadable
                # expiry means we cannot prove the link is still valid, so the
                # only safe reading is EXPIRED.
                log.warning("share token %s… has unparseable share_expires_at %r "
                            "— treating as expired", str(token)[:8], expires)
                return None
        d = dict(row)
        # Inflate data JSON blob
        try:
            d["data"] = json.loads(d.get("data") or "{}")
        except json.JSONDecodeError:
            d["data"] = {}
        return d


# ── Admin Dashboard v2 (operational cockpit) ─────────────────────────────────
#
# Read-only aggregate accessors for the /api/admin/v2 router. Two hard rules:
#   1. ALL € cost/spend comes from usage_events.cost_eur — the COMPLETE per-call
#      meter (incl. sub-readers after the 2026-07-04 fix). extractions.cost_eur
#      is PASS-1-ONLY and must never be summed for money figures.
#   2. Any caller-supplied value (search, ids) is bound as a SQL parameter —
#      never string-interpolated.
# Day bucketing keys off substr(created_at, 1, 10): created_at is written by
# _now_iso() as "YYYY-MM-DDTHH:MM:SSZ", so the first 10 chars are the UTC date.

def _window_cutoff_date(days: int) -> str:
    """Return the inclusive lower-bound date ("YYYY-MM-DD") for a `days`-wide
    window ending today (UTC). days<=0 is clamped to 1."""
    from datetime import datetime, timedelta, timezone
    days = max(1, int(days or 1))
    start = datetime.now(timezone.utc) - timedelta(days=days - 1)
    return start.strftime("%Y-%m-%d")


def admin_daily_series(days: int = 30) -> list[dict]:
    """Per-day operational time series over the last `days` (UTC), one row per
    day that has ANY activity. Each row:
      {date, signups, projects, extractions, cost_eur, revenue_eur}
    - signups   ← users.created_at
    - projects  ← projects.created_at
    - extractions ← COUNT(usage_events WHERE kind LIKE '%extract%')
    - cost_eur  ← SUM(usage_events.cost_eur)  (ALL kinds — the true spend)
    - revenue_eur ← SUM(invoices.total_eur)
    Days with no activity are omitted (the router fills gaps if it wants a dense
    calendar). Sorted ascending by date."""
    cutoff = _window_cutoff_date(days)
    buckets: dict[str, dict] = {}

    def _bucket(day: str) -> dict:
        return buckets.setdefault(day, {
            "date": day, "signups": 0, "projects": 0,
            "extractions": 0, "cost_eur": 0.0, "revenue_eur": 0.0,
        })

    with _conn() as c:
        for r in c.execute(
            """SELECT substr(created_at,1,10) AS d, COUNT(*) AS n
                 FROM users WHERE substr(created_at,1,10) >= ?
                GROUP BY d""", (cutoff,)).fetchall():
            _bucket(r["d"])["signups"] = int(r["n"])
        for r in c.execute(
            """SELECT substr(created_at,1,10) AS d, COUNT(*) AS n
                 FROM projects WHERE substr(created_at,1,10) >= ?
                GROUP BY d""", (cutoff,)).fetchall():
            _bucket(r["d"])["projects"] = int(r["n"])
        for r in c.execute(
            """SELECT substr(created_at,1,10) AS d,
                      SUM(cost_eur) AS cost,
                      SUM(CASE WHEN kind LIKE '%extract%' THEN 1 ELSE 0 END) AS extr
                 FROM usage_events WHERE substr(created_at,1,10) >= ?
                GROUP BY d""", (cutoff,)).fetchall():
            b = _bucket(r["d"])
            b["cost_eur"] = round(float(r["cost"] or 0), 4)
            b["extractions"] = int(r["extr"] or 0)
        for r in c.execute(
            """SELECT substr(created_at,1,10) AS d, SUM(total_eur) AS rev
                 FROM invoices WHERE substr(created_at,1,10) >= ?
                GROUP BY d""", (cutoff,)).fetchall():
            _bucket(r["d"])["revenue_eur"] = round(float(r["rev"] or 0), 2)

    return [buckets[d] for d in sorted(buckets)]


def admin_window_totals(days: int = 30) -> dict:
    """Aggregate totals for a `days` window (UTC), reading cost from
    usage_events (never extractions). Shape:
      {signups, projects, extractions, cost_eur, revenue_eur}"""
    cutoff = _window_cutoff_date(days)
    with _conn() as c:
        signups = c.execute(
            "SELECT COUNT(*) AS n FROM users WHERE substr(created_at,1,10) >= ?",
            (cutoff,)).fetchone()["n"]
        projects = c.execute(
            "SELECT COUNT(*) AS n FROM projects WHERE substr(created_at,1,10) >= ?",
            (cutoff,)).fetchone()["n"]
        urow = c.execute(
            """SELECT COALESCE(SUM(cost_eur),0) AS cost,
                      COALESCE(SUM(CASE WHEN kind LIKE '%extract%' THEN 1 ELSE 0 END),0) AS extr
                 FROM usage_events WHERE substr(created_at,1,10) >= ?""",
            (cutoff,)).fetchone()
        revenue = c.execute(
            "SELECT COALESCE(SUM(total_eur),0) AS rev FROM invoices WHERE substr(created_at,1,10) >= ?",
            (cutoff,)).fetchone()["rev"]
    return {
        "signups": int(signups or 0),
        "projects": int(projects or 0),
        "extractions": int(urow["extr"] or 0),
        "cost_eur": round(float(urow["cost"] or 0), 4),
        "revenue_eur": round(float(revenue or 0), 2),
    }


def admin_prior_window_totals(days: int = 30) -> dict:
    """Totals for the window IMMEDIATELY BEFORE the current one (same width),
    for delta computation. Uses the same usage_events cost rule."""
    from datetime import datetime, timedelta, timezone
    days = max(1, int(days or 1))
    now = datetime.now(timezone.utc)
    cur_start = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    prior_start = (now - timedelta(days=2 * days - 1)).strftime("%Y-%m-%d")
    with _conn() as c:
        def _between(sql: str) -> float:
            return c.execute(sql, (prior_start, cur_start)).fetchone()["v"]
        signups = _between(
            "SELECT COUNT(*) AS v FROM users "
            "WHERE substr(created_at,1,10) >= ? AND substr(created_at,1,10) < ?")
        projects = _between(
            "SELECT COUNT(*) AS v FROM projects "
            "WHERE substr(created_at,1,10) >= ? AND substr(created_at,1,10) < ?")
        urow = c.execute(
            """SELECT COALESCE(SUM(cost_eur),0) AS cost,
                      COALESCE(SUM(CASE WHEN kind LIKE '%extract%' THEN 1 ELSE 0 END),0) AS extr
                 FROM usage_events
                WHERE substr(created_at,1,10) >= ? AND substr(created_at,1,10) < ?""",
            (prior_start, cur_start)).fetchone()
        revenue = _between(
            "SELECT COALESCE(SUM(total_eur),0) AS v FROM invoices "
            "WHERE substr(created_at,1,10) >= ? AND substr(created_at,1,10) < ?")
    return {
        "signups": int(signups or 0),
        "projects": int(projects or 0),
        "extractions": int(urow["extr"] or 0),
        "cost_eur": round(float(urow["cost"] or 0), 4),
        "revenue_eur": round(float(revenue or 0), 2),
    }


def admin_cost_total_eur(days: int | None = None, today_only: bool = False) -> float:
    """SUM(usage_events.cost_eur) over a window. `today_only` restricts to the
    current UTC date; otherwise a `days` window (None = all-time)."""
    with _conn() as c:
        if today_only:
            from datetime import datetime, timezone
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            row = c.execute(
                "SELECT COALESCE(SUM(cost_eur),0) AS v FROM usage_events "
                "WHERE substr(created_at,1,10) = ?", (today,)).fetchone()
        elif days is not None:
            row = c.execute(
                "SELECT COALESCE(SUM(cost_eur),0) AS v FROM usage_events "
                "WHERE substr(created_at,1,10) >= ?", (_window_cutoff_date(days),)).fetchone()
        else:
            row = c.execute("SELECT COALESCE(SUM(cost_eur),0) AS v FROM usage_events").fetchone()
    return round(float(row["v"] or 0), 4)


def admin_top_users_by_spend(days: int = 30, limit: int = 10) -> list[dict]:
    """Top-N users by usage_events spend within the window. Each row:
      {user_id, email, spend_eur, extraction_count}.
    extraction_count = usage_events rows with kind LIKE '%extract%'."""
    cutoff = _window_cutoff_date(days)
    with _conn() as c:
        rows = c.execute(
            """SELECT ue.user_id AS user_id,
                      u.email AS email,
                      COALESCE(SUM(ue.cost_eur),0) AS spend,
                      COALESCE(SUM(CASE WHEN ue.kind LIKE '%extract%' THEN 1 ELSE 0 END),0) AS extr
                 FROM usage_events ue
                 LEFT JOIN users u ON u.id = ue.user_id
                WHERE substr(ue.created_at,1,10) >= ?
                GROUP BY ue.user_id
                ORDER BY spend DESC
                LIMIT ?""", (cutoff, int(limit))).fetchall()
    return [
        {"user_id": r["user_id"], "email": r["email"],
         "spend_eur": round(float(r["spend"] or 0), 4),
         "extraction_count": int(r["extr"] or 0)}
        for r in rows
    ]


def admin_cost_by_model(days: int = 30) -> list[dict]:
    """Per-model cost breakdown within the window: [{model, cost_eur, event_count}]."""
    cutoff = _window_cutoff_date(days)
    with _conn() as c:
        rows = c.execute(
            """SELECT COALESCE(model,'unknown') AS model,
                      COALESCE(SUM(cost_eur),0) AS cost,
                      COUNT(*) AS n
                 FROM usage_events
                WHERE substr(created_at,1,10) >= ?
                GROUP BY COALESCE(model,'unknown')
                ORDER BY cost DESC""", (cutoff,)).fetchall()
    return [
        {"model": r["model"], "cost_eur": round(float(r["cost"] or 0), 4),
         "event_count": int(r["n"])}
        for r in rows
    ]


def admin_users_over_today_threshold(threshold_eur: float) -> list[dict]:
    """Users whose usage_events spend for the current UTC date exceeds
    `threshold_eur`. Each row: {user_id, email, spend_today_eur}."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _conn() as c:
        rows = c.execute(
            """SELECT ue.user_id AS user_id, u.email AS email,
                      COALESCE(SUM(ue.cost_eur),0) AS spend
                 FROM usage_events ue
                 LEFT JOIN users u ON u.id = ue.user_id
                WHERE substr(ue.created_at,1,10) = ?
                GROUP BY ue.user_id
               HAVING spend > ?
                ORDER BY spend DESC""", (today, float(threshold_eur))).fetchall()
    return [
        {"user_id": r["user_id"], "email": r["email"],
         "spend_today_eur": round(float(r["spend"] or 0), 4)}
        for r in rows
    ]


def admin_avg_cost_per_extraction_eur(days: int = 30) -> float:
    """Window SUM(usage_events.cost_eur) / COUNT(extract-kind events). 0 when
    there are no extraction events (avoid divide-by-zero)."""
    cutoff = _window_cutoff_date(days)
    with _conn() as c:
        row = c.execute(
            """SELECT COALESCE(SUM(cost_eur),0) AS cost,
                      COALESCE(SUM(CASE WHEN kind LIKE '%extract%' THEN 1 ELSE 0 END),0) AS extr
                 FROM usage_events WHERE substr(created_at,1,10) >= ?""",
            (cutoff,)).fetchone()
    n = int(row["extr"] or 0)
    return round(float(row["cost"] or 0) / n, 4) if n else 0.0


def admin_list_users_paginated(search: str | None = None, page: int = 1,
                               limit: int = 25) -> dict:
    """Paginated + searchable user directory for admin management. Returns
    {rows, total, page, limit}. Each row includes project_count and
    total_spend_eur (SUM usage_events for that user — the true spend).

    `search` (when set) matches email / name / company_name via a PARAMETERIZED
    LIKE (case-insensitive) — the pattern is bound, never interpolated."""
    page = max(1, int(page or 1))
    limit = max(1, min(int(limit or 25), 200))
    offset = (page - 1) * limit
    where = ""
    params: list = []
    if search:
        where = ("WHERE (LOWER(u.email) LIKE ? OR LOWER(COALESCE(u.name,'')) LIKE ? "
                 "OR LOWER(COALESCE(u.company_name,'')) LIKE ?)")
        pat = f"%{search.lower()}%"
        params = [pat, pat, pat]
    with _conn() as c:
        # SAFE: {where} is a hardcoded literal template (only `?` placeholders,
        # never user input); every value flows through the bound `params` list.
        # DO NOT ever interpolate a search value into {where} — bind it. (audit)
        total = c.execute(
            f"SELECT COUNT(*) AS n FROM users u {where}", params).fetchone()["n"]
        rows = c.execute(
            f"""SELECT u.id, u.email, u.name, u.company_name, u.company_code,
                       u.plan, u.plan_status, u.is_admin, u.is_active,
                       u.created_at, u.last_login_at,
                       (SELECT COUNT(*) FROM projects p WHERE p.user_id = u.id) AS project_count,
                       (SELECT COALESCE(SUM(ue.cost_eur),0) FROM usage_events ue
                          WHERE ue.user_id = u.id) AS total_spend_eur
                  FROM users u
                  {where}
              ORDER BY u.created_at DESC
                 LIMIT ? OFFSET ?""",
            params + [limit, offset]).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["total_spend_eur"] = round(float(d.get("total_spend_eur") or 0), 4)
        d["project_count"] = int(d.get("project_count") or 0)
        out.append(d)
    return {"rows": out, "total": int(total or 0), "page": page, "limit": limit}


def set_user_active(user_id: str, active: bool) -> bool:
    """Set users.is_active (0/1). Returns False if the user doesn't exist.
    Guardrails (self / other-admin) are enforced in the router, not here."""
    with _conn() as c:
        cur = c.execute(
            "UPDATE users SET is_active = ? WHERE id = ?",
            (1 if active else 0, user_id))
        return cur.rowcount > 0


def record_admin_action(actor_id: str, action: str,
                        target_id: str | None = None,
                        detail: str | None = None) -> None:
    """Append one admin-action audit row. Call AFTER the mutation succeeds so the
    trail records what actually happened, never an attempt. `actor_id` is the
    acting admin's user id; `action` is a dotted verb (e.g. 'user.disable');
    `target_id` is the affected user (None if the action has no user target);
    `detail` is a short human-readable string (e.g. the target's email)."""
    with _conn() as c:
        c.execute("""
            INSERT INTO admin_audit_log
                (actor_user_id, action, target_user_id, detail, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (actor_id, action, target_id, detail, _now_iso()))


def list_admin_actions(limit: int = 100) -> list[dict]:
    """Most-recent admin actions first (newest → oldest), capped at `limit`.
    Ties on created_at (1-second resolution) break on the autoincrement id so
    same-second actions still read back in insertion order. LEFT JOINs users to
    surface actor/target emails for display — a since-deleted user leaves a NULL
    email, but the row (and its `detail`) still stands."""
    with _conn() as c:
        rows = c.execute("""
            SELECT a.id, a.actor_user_id, act.email AS actor_email,
                   a.action, a.target_user_id, tgt.email AS target_email,
                   a.detail, a.created_at
              FROM admin_audit_log a
              LEFT JOIN users act ON act.id = a.actor_user_id
              LEFT JOIN users tgt ON tgt.id = a.target_user_id
          ORDER BY a.created_at DESC, a.id DESC
             LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def admin_events_by_kind(days: int = 30) -> list[dict]:
    """usage_events counts grouped by kind within the window — the extraction
    success/volume signal. [{kind, count, cost_eur}]."""
    cutoff = _window_cutoff_date(days)
    with _conn() as c:
        rows = c.execute(
            """SELECT COALESCE(kind,'?') AS kind, COUNT(*) AS n,
                      COALESCE(SUM(cost_eur),0) AS cost
                 FROM usage_events WHERE substr(created_at,1,10) >= ?
                GROUP BY COALESCE(kind,'?')
                ORDER BY n DESC""", (cutoff,)).fetchall()
    return [
        {"kind": r["kind"], "count": int(r["n"]),
         "cost_eur": round(float(r["cost"] or 0), 4)}
        for r in rows
    ]


def admin_health_totals() -> dict:
    """Whole-table counts for the health screen: users, projects, extractions,
    usage_events, invoices, corrections."""
    with _conn() as c:
        def _count(tbl: str) -> int:
            return int(c.execute(f"SELECT COUNT(*) AS n FROM {tbl}").fetchone()["n"])
        return {
            "users": _count("users"),
            "projects": _count("projects"),
            "extractions": _count("extractions"),
            "usage_events": _count("usage_events"),
            "invoices": _count("invoices"),
            "corrections": _count("corrections"),
        }


def admin_recent_activity() -> dict:
    """Most-recent timestamps across the app (defensive — missing/empty → None):
    last_signup, last_project, last_usage_event, last_invoice."""
    with _conn() as c:
        def _max(sql: str):
            try:
                return c.execute(sql).fetchone()["v"]
            except Exception:
                return None
        return {
            "last_signup": _max("SELECT MAX(created_at) AS v FROM users"),
            "last_project": _max("SELECT MAX(created_at) AS v FROM projects"),
            "last_usage_event": _max("SELECT MAX(created_at) AS v FROM usage_events"),
            "last_invoice": _max("SELECT MAX(created_at) AS v FROM invoices"),
        }


def admin_db_size_bytes() -> int:
    """On-disk size of the SQLite DB file (0 if not yet materialised)."""
    try:
        return int(_DB_PATH.stat().st_size)
    except OSError:
        return 0


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


def scrub_all_projects() -> int:
    """One-shot, idempotent: rewrite every stored project blob through
    `extractor.user_text.scrub_prose` so no old prose (methodology confessions,
    another customer's project name) survives in the database. Runs at startup;
    only rows whose blob actually changes are written. Returns the count."""
    from extractor.user_text import scrub_prose
    changed = 0
    with _conn() as c:
        rows = c.execute("SELECT id, data FROM projects").fetchall()
        for row in rows:
            raw = row["data"]
            try:
                data = json.loads(raw or "{}")
            except (json.JSONDecodeError, TypeError, ValueError):
                continue  # corrupt blobs are the read path's problem, not ours
            cleaned = scrub_prose(data)
            if cleaned != data:
                c.execute("UPDATE projects SET data = ? WHERE id = ?",
                          (json.dumps(cleaned, ensure_ascii=False), row["id"]))
                changed += 1
    if changed:
        log.warning("scrub_all_projects: rewrote %d project blob(s) carrying legacy prose", changed)
    return changed
