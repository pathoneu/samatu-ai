/**
 * Session telemetry — how long a project is open, what gets corrected, and
 * whether an export leaves the building.
 *
 * Two layers:
 *   • `createSession` (Sprint 0 Fix 6) — one record per component mount, POSTed
 *     on finish. Kept for callers and tests that hold their own session.
 *   • `pilotSession(projectId)` (2026-09-13, council verdict 5) — ONE session
 *     per project per page load, shared by the drawing step, the check sheet
 *     and the sąmata table, so the pilot's questions can be answered from the
 *     log alone: minutes from opening to export, facts accepted vs corrected
 *     per room, rows priced / deleted / added, whether the export happened.
 *     Flushed with `sendBeacon` on pagehide (a normal fetch is dropped when the
 *     tab closes) and when the project changes.
 *
 * What is recorded: event type, a target {kind, id} (a fact key, a room number,
 * a row's label — never a price, a name or a client), outcome, time offset.
 * The backend appends the record to a JSONL file; `scripts/pilot_report.py`
 * reads it. Nothing here ever blocks or fails the user's flow.
 */

import { API_BASE } from './apiBase.js';

const SESSION_URL = `${API_BASE}/api/telemetry/session`;

/** Event types the pilot report understands (free strings, listed for grep). */
export const PILOT_EVENTS = Object.freeze([
  'fact_accept', 'fact_number', 'fact_choice', 'opening_adjust', 'opening_size',
  'room_verified', 'room_add', 'scope_change', 'row_edit', 'row_delete', 'row_add',
  'kainynas_apply', 'export', 'reread',
]);

export function createSession({ projectId, now = () => Date.now() }) {
  const startedAt = now();
  const gestures = [];
  let finished = false;

  return {
    recordGesture(g, gestureNow = now()) {
      if (finished) return;
      gestures.push({
        type: g.type,
        target: g.target,
        outcome: g.outcome,
        duration_ms: g.duration_ms ?? 0,
        timestamp_ms_from_start: gestureNow - startedAt,
      });
    },

    async finish({ exported = false, now: finishNow = now } = {}) {
      if (finished) return;
      finished = true;
      const finishedAt = finishNow();
      const payload = {
        project_id: projectId,
        started_at: Math.floor(startedAt / 1000),
        finished_at: Math.floor(finishedAt / 1000),
        total_seconds: Math.floor((finishedAt - startedAt) / 1000),
        gestures,
        exported,
      };
      try {
        await fetch(SESSION_URL, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } catch (err) {
        // Don't fail the user's flow on telemetry error
        console.warn('telemetry post failed:', err);
      }
    },
  };
}

// ── the shared pilot session ────────────────────────────────────────────────

const sessions = new Map();   // projectId → { startedAt, events, exported, exports }
const pendingRelease = new Map();   // projectId → timer handle
let pagehideBound = false;

function payloadOf(projectId, s, finishedAt) {
  return {
    project_id: projectId,
    started_at: Math.floor(s.startedAt / 1000),
    finished_at: Math.floor(finishedAt / 1000),
    total_seconds: Math.floor((finishedAt - s.startedAt) / 1000),
    gestures: s.events,
    exported: s.exported,
  };
}

/**
 * Send one record. `sendBeacon` survives the tab closing; a keepalive fetch is
 * the fallback where beacons do not exist (tests, old browsers).
 */
export function postSessionRecord(payload, { beacon, fetchFn } = {}) {
  const body = JSON.stringify(payload);
  const nav = typeof navigator !== 'undefined' ? navigator : undefined;
  const sendBeacon = beacon || (nav && typeof nav.sendBeacon === 'function' ? nav.sendBeacon.bind(nav) : null);
  if (sendBeacon) {
    try {
      const blob = typeof Blob !== 'undefined' ? new Blob([body], { type: 'application/json' }) : body;
      if (sendBeacon(SESSION_URL, blob)) return true;
    } catch { /* fall through to fetch */ }
  }
  const f = fetchFn || (typeof fetch === 'function' ? fetch : null);
  if (!f) return false;
  try {
    const p = f(SESSION_URL, {
      method: 'POST',
      credentials: 'include',
      keepalive: true,
      headers: { 'Content-Type': 'application/json' },
      body,
    });
    if (p && typeof p.catch === 'function') p.catch(() => {});
    return true;
  } catch {
    return false;
  }
}

function bindPagehide() {
  if (pagehideBound || typeof window === 'undefined') return;
  pagehideBound = true;
  const flush = () => flushPilotSessions();
  window.addEventListener('pagehide', flush);
  window.addEventListener('beforeunload', flush);
}

/** The project's session for this page load — created on first use. */
export function pilotSession(projectId, now = () => Date.now(), { clearTimeoutFn = clearTimeout } = {}) {
  const id = projectId == null ? '' : String(projectId);
  if (!id) return null;
  // A component that remounts (the sheet re-keys on a refreshed project, the
  // table on a step change) touches the session again within a moment —
  // cancel the release its unmount scheduled so one visit stays one session.
  const pending = pendingRelease.get(id);
  if (pending !== undefined) {
    clearTimeoutFn(pending);
    pendingRelease.delete(id);
  }
  let s = sessions.get(id);
  if (!s) {
    s = { startedAt: now(), events: [], exported: false, exports: 0 };
    sessions.set(id, s);
    bindPagehide();
  }
  return s;
}

/**
 * Record one thing the contractor did. Never throws. `target` is
 * {kind, id} — a fact key, a room nr, a row label; keep prices and names out.
 */
export function recordPilot(projectId, type, target = {}, outcome = 'success', now = () => Date.now()) {
  try {
    const s = pilotSession(projectId, now);
    if (!s) return;
    s.events.push({
      type: String(type),
      target: { kind: String(target?.kind ?? ''), id: String(target?.id ?? ''), ...(target?.room != null ? { room: String(target.room) } : {}) },
      outcome: String(outcome),
      duration_ms: 0,
      timestamp_ms_from_start: Math.max(0, now() - s.startedAt),
    });
  } catch { /* telemetry never breaks the flow */ }
}

/** An export left the app: the session's answer to „did he send it?". */
export function markExported(projectId, format = '', now = () => Date.now()) {
  const s = pilotSession(projectId, now);
  if (!s) return;
  s.exported = true;
  s.exports += 1;
  recordPilot(projectId, 'export', { kind: 'export', id: format }, 'success', now);
}

/**
 * Post and forget every open session (page hide, project switch). Sessions
 * with nothing in them and under a few seconds are noise and are dropped.
 */
export function flushPilotSessions({ now = () => Date.now(), post = postSessionRecord, minSeconds = 3 } = {}) {
  const out = [];
  for (const [id, s] of sessions) {
    const finishedAt = now();
    const p = payloadOf(id, s, finishedAt);
    if (p.total_seconds >= minSeconds || p.gestures.length > 0) {
      post(p);
      out.push(p);
    }
    sessions.delete(id);
  }
  return out;
}

/**
 * A page that showed the project is going away. Flush that project's session
 * unless the project is touched again within `delayMs` (a remount, the next
 * step of the same project) — then the visit continues as one session.
 */
export function releasePilotSession(projectId, {
  delayMs = 1500, setTimeoutFn = setTimeout, clearTimeoutFn = clearTimeout,
  now = () => Date.now(), post = postSessionRecord,
} = {}) {
  const id = projectId == null ? '' : String(projectId);
  if (!id || !sessions.has(id)) return;
  const pending = pendingRelease.get(id);
  if (pending !== undefined) clearTimeoutFn(pending);
  const handle = setTimeoutFn(() => {
    pendingRelease.delete(id);
    const s = sessions.get(id);
    if (!s) return;
    const p = payloadOf(id, s, now());
    sessions.delete(id);
    if (p.total_seconds >= 3 || p.gestures.length > 0) post(p);
  }, delayMs);
  pendingRelease.set(id, handle);
}

/** Test seam. */
export function _resetPilotSessions() {
  for (const h of pendingRelease.values()) clearTimeout(h);
  pendingRelease.clear();
  sessions.clear();
}
