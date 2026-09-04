/**
 * projectStore — durable project storage.
 *
 * Architecture (Phase 12.3 + 13):
 * - Write-through: every mutation writes to localStorage (instant UX) AND
 *   POSTs to backend /api/projects (durable, cross-device, per-user).
 * - Backend is the source of truth; localStorage is the offline cache.
 * - On Dashboard mount, pullProjectsFromBackend() syncs backend → cache.
 * - On logout (authContext), localStorage is cleared so next user starts fresh.
 *
 * Demo data is NOT seeded — auth-gated empty state on first login is correct.
 *
 * Backend POSTs use credentials: 'include' for session cookie. They're
 * fire-and-forget — UI never blocks waiting; if backend is offline,
 * localStorage still works and sync resumes when online.
 */

// Explicit .js extension so this module also resolves under plain `node --test`
// (the unit tests below import it directly, without the vite resolver).
import { API_BASE as API } from './apiBase.js';
import { toast } from 'sonner';

const PROJECTS_KEY = 'samatu_projects';
const PRICE_LISTS_KEY = 'samatu_price_lists';
const SETTINGS_KEY = 'samatu_settings';

// P7: Legacy ASCII-stripped skyrius names → modern LT-with-diacritics. Used
// to migrate old projects in localStorage so UI shows consistent names.
// Mirror of backend SKYRIUS_LEGACY_MIGRATION (extractor/vision_call.py).
// Sprint §FIX-2 (2026-04-29): expanded with GKP/glaistymas variants —
// user reported 3 separate "GKP montavimas" groups in UI from these.
// Mirror of backend SKYRIUS_LEGACY_MIGRATION (extractor/vision_call.py).
//
// 2026-09-02: 'Sienų glaistymas dažymas' was REMOVED from this map — it is now
// one of the two canonical paint sections, not a legacy alias. Rows still
// carrying the merged 'Sienų lubų glaistymas dažymas' are re-sectioned per ROW
// by `migrateSkyriusRow` below (mirror of vision_call.migrate_skyrius_row).
const SKYRIUS_LEGACY_MIGRATION = {
  // An export written by a tool that strips diacritics turns the shopping list
  // into "Medziagos"; without this it loaded as a section of its own and the
  // materials scattered away from the foot of the sąmata.
  'Medziagos': 'Medžiagos',
  'Glaistymas dazymas': 'Sienų lubų glaistymas dažymas',
  'Glaistymas dažymas': 'Sienų lubų glaistymas dažymas',
  'Plyteles': 'Plytelių klijavimas',
  'Plytelių darbai': 'Plytelių klijavimas',
  'Pridetiniai elementai': 'Pridėtiniai elementai',
  'Santechnikos darbai/ kondicionavimo darbai': 'Santechnikos darbai',
  'Elektros instaliacijos darbai/ apsvietimas': 'Elektros instaliacijos darbai',
  'Grindu darbai': 'Grindys',
  'Grindų darbai': 'Grindys',
  'Grindų danga': 'Grindys',
  // GKP variants — collapse to canonical "GKP montavimas"
  'GKP': 'GKP montavimas',
  'GKP konstrukcija': 'GKP montavimas',
  'GKP karkas': 'GKP montavimas',
  'Gipso kartono montavimas': 'GKP montavimas',
  'Gipsokartono montavimas': 'GKP montavimas',
  'GKP lubu montavimas': 'GKP montavimas',
  'GKP lubų montavimas': 'GKP montavimas',
};

const SK_GD_MERGED = 'Sienų lubų glaistymas dažymas';
const SK_GD_SIENOS = 'Sienų glaistymas dažymas';
const SK_GD_LUBOS = 'Lubų glaistymas dažymas';
// LED niches are cut into the ceiling and are glaistomos/dažomos with it.
const LUBOS_PREFIXES = ['Lubų', 'LED nišų'];

/**
 * Canonical skyrius for ONE row — the legacy name map plus the 2026-09-02
 * sienų/lubų split. Mirror of `extractor/vision_call.migrate_skyrius_row`;
 * a row's section can only be decided from its APRAŠYMAS, because the merged
 * section held both wall and ceiling work.
 */
export function migrateSkyriusRow(skyrius, aprasymas) {
  const s = (skyrius || '').trim();
  const mapped = SKYRIUS_LEGACY_MIGRATION[s] || s;
  if (mapped !== SK_GD_MERGED) return mapped;
  const a = (aprasymas || '').trim();
  return LUBOS_PREFIXES.some(pre => a.startsWith(pre)) ? SK_GD_LUBOS : SK_GD_SIENOS;
}

function _migrateProject(p) {
  if (!p || typeof p !== 'object') return p;
  const migrated = { ...p };
  // Migrate skyrius names in darbu_sarasas
  if (Array.isArray(p.darbu_sarasas)) {
    migrated.darbu_sarasas = p.darbu_sarasas.map(it => {
      if (!it || typeof it !== 'object') return it;
      const newSk = migrateSkyriusRow(it.skyrius, it.aprasymas || it.pavadinimas);
      const newSkLabel = it.skyrius_label
        ? migrateSkyriusRow(it.skyrius_label, it.aprasymas || it.pavadinimas)
        : it.skyrius_label;
      if (newSk !== it.skyrius || newSkLabel !== it.skyrius_label) {
        return { ...it, skyrius: newSk, skyrius_label: newSkLabel };
      }
      return it;
    });
  }
  // Same for pozicijos
  if (Array.isArray(p.pozicijos)) {
    migrated.pozicijos = p.pozicijos.map(it => {
      if (!it || typeof it !== 'object') return it;
      const newSk = migrateSkyriusRow(it.skyrius, it.aprasymas);
      return newSk !== it.skyrius ? { ...it, skyrius: newSk } : it;
    });
  }
  return migrated;
}

// ── Quota-safe localStorage writes ────────────────────────────────────────────
// A project blob with polygons + measurements is easily 1-2 MB; a handful of
// them plus a base64 logo hits the ~5 MB origin quota. setItem then throws
// QuotaExceededError and, before this helper, that exception escaped through
// updateProject into the React handler — the click looked like a no-op and the
// user lost the edit with no explanation. Now: warn ONCE per session, keep the
// backend write-through (which is the real source of truth) running.

let _storageNoticeShown = false;

// Test hook — lets the unit test assert the "warned once" behaviour.
export function _hasStorageNotice() {
  return _storageNoticeShown;
}

function _persist(key, value) {
  try {
    localStorage.setItem(key, value);
    return true;
  } catch (e) {
    console.warn('[projectStore] localStorage write failed:', e);
    if (!_storageNoticeShown) {
      _storageNoticeShown = true;
      toast.error(
        'Naršyklės atmintis pilna — pakeitimai neišsaugoti šioje naršyklėje. '
        + 'Ištrinkite senus projektus arba logotipą.',
        { id: 'projectstore-quota' },
      );
    }
    return false;
  }
}

// ── Backend sync helpers (fire-and-forget) ────────────────────────────────────

// Classify a write-through response and tell the user when the save did NOT
// reach the backend. Before this, `_syncToBackend` only caught network errors —
// an expired session (401) or a 500 was swallowed, so the user kept editing
// against a backend that had stopped accepting the writes and lost everything
// on the next device / after a cache clear.
// Returns 'ok' | 'unauthorized' | 'conflict' | 'failed' (return value exists
// for the tests).
export function _handleSyncResponse(res) {
  if (res?.status === 401) {
    toast.error('Sesija baigėsi — prisijunkite iš naujo. '
      + 'Paskutinis pakeitimas neišsaugotas serveryje.');
    if (typeof window !== 'undefined') window.location.assign('/login');
    return 'unauthorized';
  }
  if (res?.status === 409) {
    // Lost-update guard (2026-07-28). The backend refused the write because
    // the project moved on since we loaded it — another tab or device saved
    // first. Overwriting would silently destroy their work, so we say so and
    // keep OUR unsaved copy in this tab (the user can copy values out before
    // reloading). One toast id → a burst of saves can't stack notifications.
    toast.error('Projektas atnaujintas kitame lange — perkraukite puslapį '
      + '(pakeitimai neįrašyti)', { id: 'projectstore-conflict' });
    return 'conflict';
  }
  if (!res?.ok) {
    toast.error(`Nepavyko išsaugoti serveryje (${res?.status ?? '—'}). `
      + 'Pakeitimai išliks šioje naršyklėje.', { id: 'projectstore-sync' });
    return 'failed';
  }
  return 'ok';
}

function _handleSyncError(e) {
  console.warn('[projectStore] backend sync failed:', e);
  toast.error('Nepavyko pasiekti serverio — pakeitimai išsaugoti tik šioje naršyklėje.',
    { id: 'projectstore-sync' });
}

// ── Optimistic-concurrency bookkeeping ────────────────────────────────────────
// The updated_at the SERVER last told us about, per project id. It is NOT
// project.updated_at — updateProject() stamps that optimistically on every local
// edit, so it drifts ahead of the server immediately. Populated from the backend
// pull and from each successful PUT response; sent back as `base_updated_at` so
// the backend can refuse a write that would clobber another tab.
const _serverVersions = new Map();

export function _getServerVersion(id) {   // test hook
  return _serverVersions.get(id);
}

// Adopt a server-side version stamp produced OUTSIDE the PUT path — e.g. the
// revalidate endpoint persists on the server and returns the new updated_at.
// Without re-basing here, the tab's next write-through carries a stale
// base_updated_at, trips the 409 guard below and falsely reports lost work.
export function noteServerVersion(id, updatedAt) {
  if (id && updatedAt) _serverVersions.set(id, updatedAt);
}

// In-flight PUT per project id — used to supersede a slow earlier request so a
// PUT can never land after a newer one for the same project on a lossy link.
const _inflight = new Map();   // id -> AbortController
const _lastSeq = new Map();    // id -> monotonically increasing sequence number
let _seqCounter = 0;

const _syncToBackend = (project, { keepArchiveFlags = false } = {}) => {
  if (!project?.id) return;
  const id = project.id;
  // Archive flags are persisted server-side SINCE 2026-07-15 (pre-prod QA:
  // localStorage-only soft-delete meant "deleted" projects resurrected after
  // logout / on a second device). archiveProject syncs WITH the flags;
  // ordinary content saves still strip them so a stale in-memory copy can't
  // accidentally flip archive state — archive/restore are the only writers.
  // (Backend PUT replaces the whole blob, so restoreProject syncing a
  // flag-less object clears them server-side too.)
  const { _archived, _archived_at, ...stripped } = project;
  const persisted = keepArchiveFlags ? project : stripped;
  const base = _serverVersions.get(id);
  const body = base ? { ...persisted, base_updated_at: base } : persisted;

  // Supersede any PUT still in flight for THIS project. Two overlapping saves
  // on a slow connection could otherwise arrive out of order and resurrect the
  // older blob; aborting means the newer request is always the last one the
  // server sees.
  const prev = _inflight.get(id);
  if (prev) { try { prev.abort(); } catch { /* already settled */ } }
  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  if (controller) _inflight.set(id, controller);
  const seq = ++_seqCounter;
  _lastSeq.set(id, seq);

  return fetch(`${API}/api/projects/${id}`, {
    method: 'PUT',
    credentials: 'include',
    ...(controller ? { signal: controller.signal } : {}),
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(async (res) => {
    if (_lastSeq.get(id) !== seq) return 'superseded';   // a newer PUT started
    _inflight.delete(id);
    const verdict = _handleSyncResponse(res);
    if (verdict === 'ok') {
      // Track what the server now holds so the NEXT save carries a fresh base.
      try {
        const saved = await res.json();
        if (saved?.updated_at) _serverVersions.set(id, saved.updated_at);
      } catch { /* body not JSON — leave the old base, worst case a false 409 */ }
    }
    return verdict;
  }).catch((e) => {
    if (e?.name === 'AbortError' || _lastSeq.get(id) !== seq) return 'superseded';
    _inflight.delete(id);
    _handleSyncError(e);
    return 'failed';
  });
};

// ── Debounced save layer (2026-07-28 perf sweep) ──────────────────────────────
//
// updateProject() used to do a full JSON.stringify of EVERY project into
// localStorage (13.7 ms of main thread at 20 projects) plus a ~100-190 KB
// backend PUT — synchronously, per call. A per-keystroke editor (room heights,
// wall thickness in Prielaidos) therefore fired one of each per character.
//
// Now every updateProject writes to an in-memory snapshot immediately (so
// getProjects() is always consistent — no read-your-writes hazard) and the
// EXPENSIVE half (localStorage serialize + PUT) is coalesced onto a 400 ms
// trailing timer. Last write wins per project id.
//
// One-shot user intents (create / archive / restore / delete / import / seed)
// do NOT wait: they schedule and flush in the same tick, so their semantics are
// unchanged.
const SAVE_DEBOUNCE_MS = 400;

let _memProjects = null;      // Array | null — authoritative once set
let _lsDirty = false;         // localStorage behind _memProjects?
let _saveTimer = null;
const _dirtyIds = new Set();          // project ids with a pending backend PUT
const _pendingOpts = new Map();       // id -> _syncToBackend options

function _readProjectsRaw() {
  if (_memProjects) return _memProjects;
  try {
    return JSON.parse(localStorage.getItem(PROJECTS_KEY) || '[]');
  } catch {
    return [];
  }
}

function _scheduleSave(projects, id, opts) {
  _memProjects = projects;
  _lsDirty = true;
  if (id) {
    _dirtyIds.add(id);
    if (opts) _pendingOpts.set(id, opts);
  }
  if (_saveTimer) clearTimeout(_saveTimer);
  _saveTimer = setTimeout(() => { _saveTimer = null; _doFlush(); }, SAVE_DEBOUNCE_MS);
}

function _doFlush() {
  if (_lsDirty && _memProjects) {
    // QUOTA SAFETY (verified 2026-07-28 audit, item A5). Before the in-memory
    // snapshot, a failed _persist left localStorage holding edit N-1 while the
    // caller carried on: the NEXT edit re-read that stale array, merged onto it
    // and PUT the result — silently reverting edit N on the server. That hazard
    // is gone, because every read goes through _readProjectsRaw() → _memProjects
    // whenever a save is pending, so the merge base is always the newest state
    // regardless of what localStorage accepted. localStorage is a cache here;
    // the backend PUT below still carries the full, correct blob.
    // Keep the dirty flag set when the write was refused so a later flush
    // retries it (e.g. after the user frees space by deleting a project).
    _lsDirty = !_persist(PROJECTS_KEY, JSON.stringify(_memProjects));
  }
  if (_dirtyIds.size === 0) return [];
  const ids = Array.from(_dirtyIds);
  _dirtyIds.clear();
  const pushes = [];
  for (const id of ids) {
    const proj = (_memProjects || []).find(p => p.id === id);
    if (!proj) continue;   // deleted before the flush — nothing to push
    const opts = _pendingOpts.get(id);
    _pendingOpts.delete(id);
    const verdict = _syncToBackend(proj, opts || {});
    pushes.push(Promise.resolve(verdict).then(v => ({ id, verdict: v || 'ok' })));
  }
  return pushes;
}

/**
 * Force any pending save out NOW (localStorage + backend PUT).
 *
 * Call sites: page unload/hide, and project unmount — leaving the editor must
 * never strand the last 400 ms of typing. Those callers ignore the return
 * value; it exists so a caller that has something to LOSE if the write is
 * refused can await the server's verdict — see the automatic price fill in
 * ProjectDetail, whose prices lived only in this browser's cache when the PUT
 * came back 409 and nothing ever retried. (2026-09-02)
 *
 * @returns {Promise<Array<{id: string, verdict: string}>>} one entry per PUT
 *   this flush started ('ok' | 'conflict' | 'unauthorized' | 'failed' |
 *   'superseded'); empty when there was nothing pending.
 */
export function flushProjectSaves() {
  if (_saveTimer) { clearTimeout(_saveTimer); _saveTimer = null; }
  return Promise.all(_doFlush() || []);
}

/** Write immediately — for one-shot intents that must not sit on a timer. */
function _saveNow(projects, id, opts) {
  _scheduleSave(projects, id, opts);
  flushProjectSaves();
}

/** Replace the whole cache (backend pull / backup import) — no pending state. */
function _replaceAll(projects) {
  if (_saveTimer) { clearTimeout(_saveTimer); _saveTimer = null; }
  _dirtyIds.clear();
  _pendingOpts.clear();
  _memProjects = projects;
  _lsDirty = false;
  _persist(PROJECTS_KEY, JSON.stringify(projects));
}

// Test hook — lets a unit test start from a clean slate. Shares the production
// teardown (resetPullCache) so a test can never pass against state the real
// user-switch path leaves behind.
export function _resetSaveState() {
  resetPullCache();
  _lastSeq.clear();
  _seqCounter = 0;
}

if (typeof window !== 'undefined') {
  // `visibilitychange → hidden` is the one that reliably fires on tab switch,
  // app switch and close, while the page is still fully alive — it does the
  // real work. pagehide/beforeunload are belt-and-braces for the paths it
  // misses. The localStorage half of the flush is synchronous and therefore
  // guaranteed; the PUT is best-effort at that point (a >64 KB body rules out
  // fetch keepalive), which is exactly why the visibilitychange hook matters.
  const flush = () => { try { flushProjectSaves(); } catch { /* never block unload */ } };
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flush();
  });
  window.addEventListener('pagehide', flush);
  window.addEventListener('beforeunload', flush);
}

const _deleteFromBackend = (id) => {
  fetch(`${API}/api/projects/${id}`, { method: 'DELETE', credentials: 'include' })
    .then(_handleSyncResponse)
    .catch(_handleSyncError);
};

// ── One-way pull (backend → localStorage) on app load ─────────────────────────
// Called from useProjectsSync hook below. Refreshes localStorage from backend
// to handle: (a) cross-device, (b) localStorage cleared, (c) project edited
// from another tab/session.

let _hasPulled = false;
// Sentinel for "the backend says this project is GONE (404)" — distinct from
// "the fetch for it failed", which must not shrink the cache. See the pull.
const _GONE = Symbol('gone');
// Sprint §AUDIT (2026-04-29): exported reset so authContext.logout() can
// clear the once-per-session guard. Without this, user A's archived flag
// would carry into user B's session in the same tab.
export function resetPullCache() {
  _hasPulled = false;
  // 2026-07-28: the debounced save layer keeps an IN-MEMORY snapshot of the
  // projects array, and authContext.purgeLocalUserData() only clears
  // localStorage — so on a user switch in the same tab, getProjects() would
  // have kept serving user A's projects to user B. Drop it here, at the one
  // call site the auth layer already uses.
  //
  // A pending save is deliberately DISCARDED rather than flushed: the session
  // cookie now belongs to the new user, so pushing A's blob would either 403 on
  // the ownership barrier or (worse) write under the wrong owner. Losing the
  // last <400 ms of typing on an explicit logout is the safe trade — and the
  // project page's unmount flush has usually already fired.
  if (_saveTimer) { clearTimeout(_saveTimer); _saveTimer = null; }
  _memProjects = null;
  _lsDirty = false;
  _dirtyIds.clear();
  _pendingOpts.clear();
  for (const c of _inflight.values()) { try { c.abort(); } catch { /* settled */ } }
  _inflight.clear();
  _serverVersions.clear();
  // Price lists are user-scoped and backend-backed since 2026-09-02 — releasing
  // their once-per-session guard here is what makes the NEXT user's first
  // Kainynai visit fetch his own lists instead of reusing the previous pull.
  // (authContext.purgeLocalUserData already drops the cached rows themselves.)
  _hasPulledPriceLists = false;
}
export async function pullProjectsFromBackend({ force = false } = {}) {
  if (_hasPulled && !force) return null;
  _hasPulled = true;
  // The pull REPLACES the cache — anything still sitting on the debounce timer
  // would be thrown away. Push it first.
  flushProjectSaves();
  try {
    const res = await fetch(`${API}/api/projects`, { credentials: 'include' });
    if (res.status === 401) {
      // Not authenticated — caller (AuthProvider) handles redirect; clear cache.
      _replaceAll([]);
      localStorage.removeItem(PROJECTS_KEY);
      return null;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { projects: list = [] } = await res.json();

    // Backend is source of truth — replace cache fully (don't merge old localStorage
    // entries from a previous user/session; we cleared on logout but this is defensive).
    // 2026-07-15: archive state now rides the backend blob (archiveProject
    // syncs the flags), so the pull no longer needs the localStorage archive
    // map that used to paper over a frontend-only soft-delete — and that
    // resurrected "deleted" projects after logout or on a second device.

    if (list.length === 0) {
      _replaceAll([]);
      return [];
    }

    // Backend returns SUMMARIES — fetch full data per project.
    // `.catch(() => null)`: without it ONE dropped connection rejected the whole
    // Promise.all and aborted the pull; with it a failed project is just a null
    // entry, handled by the completeness check below. A 404 is NOT a failure —
    // the project was deleted between the list and the detail call, and
    // treating it as one would block every future pull forever.
    const fulls = await Promise.all(
      list.map(p => fetch(`${API}/api/projects/${p.id}`, { credentials: 'include' })
                     .then(r => r.ok ? r.json() : (r.status === 404 ? _GONE : null))
                     .catch(() => null))
    );
    // 2026-07-28 audit: `_replaceAll(valid)` on a PARTIAL fan-out SHRANK the
    // cache — one 500 / flaky socket on a single project and it vanished from
    // the dashboard, which to the user is indistinguishable from data loss. A
    // partial pull now changes nothing: the cache keeps what it had and the
    // once-per-session guard is released, so the next Dashboard focus/mount
    // retries and can complete.
    if (fulls.some(f => f === null)) {
      const ok = fulls.filter(f => f && f !== _GONE).length;
      console.warn('[projectStore] partial pull:'
        + ` ${ok}/${list.length} projects loaded — cache left untouched`);
      _hasPulled = false;
      return null;
    }
    const valid = fulls.filter(f => f && f !== _GONE).sort((a, b) =>
      (b.updated_at || b.created_date || '').localeCompare(a.updated_at || a.created_date || '')
    );
    // Record the server's timestamp per project — the base for the next save's
    // conflict check. Without this the first PUT after a load carries no base
    // and a two-tab overwrite would still go through unnoticed.
    for (const p of valid) {
      if (p?.id && p.updated_at) _serverVersions.set(p.id, p.updated_at);
    }
    _replaceAll(valid);
    return valid;
  } catch (e) {
    console.warn('[projectStore] pull from backend failed:', e);
    // Release the once-per-session guard: a pull that never landed must not
    // pin the app to the localStorage cache until the next logout.
    _hasPulled = false;
    return null;
  }
}

// ── Projects CRUD (sync API, async backend write-through) ─────────────────────

// Kept in sync with DEMO_PROJECT.id in `@/demoData` (imported lazily there to
// keep the sample blob out of the main bundle, hence the literal here).
export const DEMO_PROJECT_ID = 'demo-objektas-a';

export function getProjects() {
  // Reads the in-memory snapshot when a debounced save is pending, so a caller
  // that mutates twice in a row (updateRoomPolygon → updateProject, or two
  // keystrokes) never reads back a stale array and drops the first edit.
  const raw = _readProjectsRaw();
  // P7 migration: legacy skyrius mojibake → modern LT names. Pure-function
  // pass — doesn't write back, so old saves stay untouched until next save.
  if (!Array.isArray(raw)) return [];
  // The sample project was re-issued under a new id. A browser that seeded the
  // previous one still holds it — drop it here so the dashboard never lists two
  // samples, and so the next save persists the removal. `is_demo` is set only
  // by DEMO_PROJECT, and the sample is local-only, so nothing is sent to the
  // backend and no real project can match.
  return raw
    .filter(p => !(p?.is_demo && p?.id !== DEMO_PROJECT_ID))
    .map(_migrateProject);
}

export function getProject(id) {
  return getProjects().find(p => p.id === id) || null;
}

// Seed the read-only sample project (real Objektas A extraction + demo prices)
// so a prospect can explore a complete, priced sąmata without uploading a PDF.
// Stable id (no duplicate on re-click); local-only — NOT synced to the backend.
export async function seedDemoProject() {
  const projects = getProjects();
  const existing = projects.find(p => p.id === DEMO_PROJECT_ID);
  if (existing) return existing;
  const { DEMO_PROJECT } = await import('@/demoData');
  const demo = { ...DEMO_PROJECT, updated_at: new Date().toISOString() };
  projects.unshift(demo);
  _saveNow(projects, null);   // local-only: no backend id to mark dirty
  return demo;
}

export function createProject(data) {
  const project = {
    ...data,
    id: crypto.randomUUID(),
    created_date: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  const projects = getProjects();
  projects.unshift(project); // newest first
  _saveNow(projects, project.id);
  return project;
}

export function updateProject(id, updates) {
  const projects = getProjects();
  const idx = projects.findIndex(p => p.id === id);
  if (idx < 0) {
    // 2026-07-28 audit: this returned null SILENTLY and 18 call sites carried
    // on as if the save had happened — the editor even cleared its "unsaved"
    // flag. The id can go missing for real reasons (another tab deleted the
    // project, a user switch wiped the cache, a stale route param), and every
    // one of them ends with the user's edits going nowhere. Return null still
    // (the call sites' contract) but SAY so. One toast id → a keystroke burst
    // can't stack notifications.
    console.warn('[projectStore] updateProject: project not found:', id);
    toast.error('Nepavyko išsaugoti — projektas nerastas. Perkraukite puslapį.',
      { id: 'projectstore-missing' });
    return null;
  }
  projects[idx] = { ...projects[idx], ...updates, updated_at: new Date().toISOString() };
  // THE hot path — debounced. Everything else in this module saves immediately.
  _scheduleSave(projects, id);
  return projects[idx];
}

// Sprint §28 (2026-04-29): soft delete with 30d restore window.
// Hard delete preserved as `permanentlyDeleteProject` for the Trash view.

const ARCHIVE_RETENTION_DAYS = 30;

export function deleteProject(id) {
  // Backwards-compatible: now soft-deletes (archives) instead of hard delete.
  // To purge immediately, call permanentlyDeleteProject(id).
  archiveProject(id);
}

export function archiveProject(id) {
  const all = getProjects();
  const target = all.find(p => p.id === id);
  if (!target) return;
  target._archived = true;
  target._archived_at = new Date().toISOString();
  // Soft-delete is durable: persist the flags server-side so the project stays
  // deleted after logout / on another device (data itself is preserved until
  // the purge window expires — restore stays possible from Šiukšliadėžė).
  _saveNow(all, id, { keepArchiveFlags: true });
}

export function restoreProject(id) {
  const all = getProjects();
  const target = all.find(p => p.id === id);
  if (!target) return;
  delete target._archived;
  delete target._archived_at;
  // PUT replaces the whole blob → syncing the flag-less object un-archives
  // server-side as well.
  _saveNow(all, id);
}

export function permanentlyDeleteProject(id) {
  const projects = getProjects().filter(p => p.id !== id);
  // Drop any pending PUT for this id and abort one in flight — a save that
  // landed AFTER the DELETE would resurrect the project server-side.
  _dirtyIds.delete(id);
  _pendingOpts.delete(id);
  const inflight = _inflight.get(id);
  if (inflight) { try { inflight.abort(); } catch { /* already settled */ } }
  _inflight.delete(id);
  _lastSeq.set(id, ++_seqCounter);   // invalidate any late response
  _serverVersions.delete(id);
  _saveNow(projects, null);
  _deleteFromBackend(id);
}

export function getArchivedProjects() {
  return getProjects().filter(p => p._archived === true);
}

export function purgeExpiredArchive() {
  const cutoff = Date.now() - ARCHIVE_RETENTION_DAYS * 86400 * 1000;
  const archived = getArchivedProjects();
  const expired = archived.filter(p => {
    const ts = p._archived_at ? new Date(p._archived_at).getTime() : 0;
    return ts > 0 && ts < cutoff;
  });
  for (const p of expired) {
    permanentlyDeleteProject(p.id);
  }
  return expired.length;
}

// ── Phase C-1 (2026-04-29): manual polygon → room.polygon_pdf bridge ─────────
//
// When the user manually traces a polygon over a room in the Phase C-1
// editor, mirror it onto the project's patalpos[].polygon_pdf field so the
// existing AiRoomOverlay/TraceOverlay renderers (already polygon-aware) pick
// it up automatically and so interiorCalc has a precise plotas_m2 to work
// from. If a patalpa with the given nr doesn't exist yet, append a new one
// (manual-traced rooms with synthetic nrs like M1/M2 from the polygon editor).

/**
 * Write a manually-traced polygon onto a room.
 *
 * Stores polygon in PDF point coordinates (matches polygon_pdf schema in
 * vision_call.py / AiRoomOverlay).
 *
 * INVARIANT: polygonPoints and pageMeta.pixels_per_meter MUST be in the same
 * coordinate space (both PDF points OR both canvas pixels). Caller is
 * responsible for the conversion before invoking this helper.
 *
 * @param projectId       Project UUID
 * @param roomNr          Room number / id (string or number)
 * @param polygonPoints   [[x, y], ...] in PDF points
 * @param pageMeta        { page_nr, page_width_pdf, page_height_pdf,
 *                          pixels_per_meter? }
 * @param roomMeta        Optional metadata for newly-appended patalpa
 *                        ({ pavadinimas, paskirtis, lubu_aukstis_m })
 */
export function updateRoomPolygon(projectId, roomNr, polygonPoints, pageMeta, roomMeta = {}) {
  const projects = getProjects();
  const proj = projects.find(p => p.id === projectId);
  if (!proj) return null;

  // Project shape is FLAT (verified 2026-04-29) — patalpos is at top-level,
  // not nested under proj.data.
  const rooms = Array.isArray(proj.patalpos) ? [...proj.patalpos] : [];
  const roomIdx = rooms.findIndex(r => String(r.nr) === String(roomNr));

  // Compute area in m² via shoelace if scale available.
  // NOTE: polygon points are in caller's coordinate space; pixels_per_meter
  // must be in the same space (see INVARIANT in JSDoc above). The shoelace
  // result is in (whatever-units)², which we convert to m² by dividing by
  // pixels_per_meter² in the matching space.
  let plotasM2 = null;
  if (pageMeta?.pixels_per_meter && polygonPoints.length >= 3) {
    let sum = 0;
    for (let i = 0; i < polygonPoints.length; i++) {
      const [x1, y1] = polygonPoints[i];
      const [x2, y2] = polygonPoints[(i + 1) % polygonPoints.length];
      sum += x1 * y2 - x2 * y1;
    }
    const areaPolygonUnits = Math.abs(sum) / 2;
    plotasM2 = Math.round(
      (areaPolygonUnits / (pageMeta.pixels_per_meter * pageMeta.pixels_per_meter)) * 100,
    ) / 100;
  }

  const polygonFields = {
    polygon_pdf: polygonPoints,
    page_width_pdf: pageMeta?.page_width_pdf,
    page_height_pdf: pageMeta?.page_height_pdf,
    page_nr: pageMeta?.page_nr,
    polygon_source: 'manual',
    polygon_confidence: 'high',
    polygon_traced_at: new Date().toISOString(),
    ...(plotasM2 != null && {
      plotas_m2: plotasM2,
      plotas_source: 'manual_polygon',
    }),
  };

  if (roomIdx >= 0) {
    rooms[roomIdx] = { ...rooms[roomIdx], ...polygonFields };
  } else {
    // Manual-only room — append. Nr stays as caller-supplied (e.g. "M1").
    // page_nr and puslapio_nr are semantically the same value here (both
    // refer to the PDF page index where the polygon was traced) — set BOTH
    // because WorkspacePanel.onJumpToPage reads puslapio_nr while overlays
    // read page_nr. eksplikacija_row_bbox is explicitly null for manual
    // rooms (no eksplikacija row) so downstream branches that null-check
    // it don't blow up on undefined.
    rooms.push({
      nr: roomNr,
      pavadinimas: roomMeta.pavadinimas || `Patalpa ${roomNr}`,
      paskirtis: roomMeta.paskirtis || 'gyvenamoji',
      lubu_aukstis_mm: roomMeta.lubu_aukstis_m
        ? Math.round(roomMeta.lubu_aukstis_m * 1000)
        : 2820,
      puslapio_nr: pageMeta?.page_nr,
      eksplikacija_row_bbox: null,
      ...polygonFields,
    });
  }

  const result = updateProject(projectId, { patalpos: rooms });

  // Phase C-1 Task 21: notify listeners (InteriorProject, ProjectMainView etc.)
  // that the project's room geometry changed and downstream kiekiai must be
  // recomputed via interiorCalc / /recompute-interior. Custom event keeps the
  // store decoupled from React; consumers subscribe with
  //   window.addEventListener('samatu:project-recompute', e => …)
  // and check e.detail.projectId to filter.
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('samatu:project-recompute', {
      detail: { projectId, reason: 'polygon-traced', roomNr },
    }));
  }

  return result;
}

/**
 * Phase C-2 (2026-05-02): one-click "✓ patvirtinta" — user confirms the
 * AI's plotas_m2 without tracing a polygon. Sets user_verified_at on the
 * patalpa; the frontend confidence calculator promotes the badge to 🟢.
 *
 * No coordinate-space mess (unlike updateRoomPolygon) because we're not
 * touching geometry — just a single timestamp.
 */
export function markRoomVerified(projectId, roomNr) {
  const projects = getProjects();
  const proj = projects.find((p) => p.id === projectId);
  if (!proj) return;
  // Stamp BOTH room arrays: the panel/sheet read `v8_rooms` when it has rooms
  // (see AssumptionsPanel.panelRooms), so stamping `patalpos` alone left the
  // room-sheet counter at „0 iš 11" after a verification (2026-09-04).
  const stamp = new Date().toISOString();
  const patch = {};
  let found = false;
  for (const key of ['patalpos', 'v8_rooms']) {
    const rooms = Array.isArray(proj[key]) ? [...proj[key]] : null;
    if (!rooms) continue;
    const idx = rooms.findIndex((r) => String(r?.nr) === String(roomNr));
    if (idx < 0) continue;
    rooms[idx] = { ...rooms[idx], user_verified_at: stamp };
    patch[key] = rooms;
    found = true;
  }
  if (!found) return;
  updateProject(projectId, patch);
  // Trigger downstream recompute (matches the pattern from updateRoomPolygon).
  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new CustomEvent('samatu:project-recompute', {
        detail: { projectId, reason: 'room-verified', roomNr },
      }),
    );
  }
}

// ── Correction audit log (Phase 12.3 learning loop foundation) ────────────────

export function logCorrection(projectId, payload) {
  if (!projectId || !payload?.field_path) return Promise.resolve(false);
  return fetch(`${API}/api/projects/${projectId}/corrections`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
    .then(res => res.ok)
    .catch((e) => {
      console.warn('[projectStore] correction log failed:', e);
      return false;
    });
}

/**
 * This project's correction log, newest first — the „Mokymosi žurnalas".
 *
 * Read-only and best-effort: the counter and the list are a reassurance that
 * the fix was written down, so a failed read must degrade to an empty list, not
 * to an error screen over the sąmata.
 */
export async function fetchCorrections(projectId, { limit = 200 } = {}) {
  if (!projectId) return [];
  try {
    const res = await fetch(
      `${API}/api/projects/${projectId}/corrections?limit=${limit}`,
      { credentials: 'include' });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data?.corrections) ? data.corrections : [];
  } catch (e) {
    console.warn('[projectStore] corrections read failed:', e);
    return [];
  }
}

// ── Price Lists (kainynai) ───────────────────────────────────────────────────
//
// WRITE-THROUGH since 2026-09-02, mirroring projects: localStorage is the cache
// for instant, synchronous reads (the apply-dropdown and the auto-fill both need
// the list without awaiting), the backend `price_lists` table is the source of
// truth. Before this, a kainynas existed in exactly one browser profile — the
// artefact the contractor had typed by hand was the least durable thing in the
// product.
//
// Reads stay SYNCHRONOUS on purpose; `pullPriceListsFromBackend()` refreshes the
// cache (Dashboard mount, the Kainynai page, and right before an automatic
// fill), and every mutation pushes to the backend fire-and-forget.

let _hasPulledPriceLists = false;
// Writes still on the wire. The pull REPLACES the cache, so it has to wait for
// them: measured in the browser 2026-09-02 — import a kainynas, the page
// invalidates its query, the force-pull overtakes the fire-and-forget PUT and
// the freshly imported list vanished from the list view until the next reload.
const _priceListWrites = new Set();

/** Resolve once every pending price-list write has settled. */
export async function flushPriceListWrites() {
  while (_priceListWrites.size) {
    await Promise.allSettled(Array.from(_priceListWrites));
  }
}

function _trackPriceListWrite(p) {
  const tracked = p.finally(() => _priceListWrites.delete(tracked));
  _priceListWrites.add(tracked);
  return tracked;
}

function _priceListsSyncToBackend(pl) {
  if (!pl?.id) return;
  return _trackPriceListWrite(fetch(`${API}/api/price-lists/${pl.id}`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: pl.name,
      company_name: pl.company_name,
      items: pl.items || [],
      is_default: !!pl.is_default,
      created_date: pl.created_date,
    }),
  }).then(_handleSyncResponse).catch(_handleSyncError));
}

function _writePriceLists(lists) {
  _persist(PRICE_LISTS_KEY, JSON.stringify(lists));
  return lists;
}

export function getPriceLists() {
  try {
    const raw = JSON.parse(localStorage.getItem(PRICE_LISTS_KEY) || '[]');
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

/**
 * Refresh the cache from the backend. Once per session unless forced — the
 * payload carries every item of every list, so it is not something to re-fetch
 * on each render.
 *
 * A failed pull leaves the cache ALONE (same rule as projects): a network blip
 * must never look like "your kainynai are gone".
 */
export async function pullPriceListsFromBackend({ force = false } = {}) {
  if (_hasPulledPriceLists && !force) return null;
  _hasPulledPriceLists = true;
  // The pull replaces the cache — anything still in flight must land first, or
  // it is thrown away before the server has even seen it.
  await flushPriceListWrites();
  try {
    const res = await fetch(`${API}/api/price-lists`, { credentials: 'include' });
    if (res.status === 401) {
      _hasPulledPriceLists = false;
      return null;                       // caller (AuthProvider) handles the redirect
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { price_lists: list = [] } = await res.json();
    if (!Array.isArray(list)) throw new Error('bad payload');
    _writePriceLists(list);
    return list;
  } catch (e) {
    console.warn('[projectStore] price list pull failed:', e);
    _hasPulledPriceLists = false;        // let the next mount retry
    return null;
  }
}

export function createPriceList(data) {
  const pl = {
    ...data,
    id: crypto.randomUUID(),
    created_date: new Date().toISOString(),
    is_default: !!data?.is_default,
  };
  const lists = getPriceLists();
  if (pl.is_default) for (const other of lists) other.is_default = false;
  lists.unshift(pl);
  _writePriceLists(lists);
  _priceListsSyncToBackend(pl);
  return pl;
}

export function deletePriceList(id) {
  _writePriceLists(getPriceLists().filter(p => p.id !== id));
  _trackPriceListWrite(
    fetch(`${API}/api/price-lists/${id}`, { method: 'DELETE', credentials: 'include' })
      .then((res) => {
        // A 404 means the backend never had it (an older localStorage-only list)
        // — that is a successful delete, not a failure to report.
        if (res.status !== 404) _handleSyncResponse(res);
      })
      .catch(_handleSyncError),
  );
}

/**
 * Mark one kainynas as the default used for automatic price fill, or clear the
 * flag when it is already the default. Exactly one default per user — enforced
 * here for the cache and again server-side for the durable copy.
 */
export function setDefaultPriceList(id) {
  const lists = getPriceLists();
  const target = lists.find(p => p.id === id);
  if (!target) return null;
  const nextValue = !target.is_default;
  const changed = [];
  for (const pl of lists) {
    const want = nextValue && pl.id === id;
    if (!!pl.is_default !== want) { pl.is_default = want; changed.push(pl); }
  }
  _writePriceLists(lists);
  // Push the flipped rows only. The backend clears the other defaults itself,
  // but pushing them keeps the two copies identical even if that write races.
  for (const pl of changed) _priceListsSyncToBackend(pl);
  return target;
}

export function getDefaultPriceList() {
  return getPriceLists().find(p => p?.is_default) || null;
}

// ── "this extraction still needs its automatic price fill" hand-off ───────────
//
// The happy path fills prices INSIDE the payload NewProject creates, so nothing
// is pending. But when the stream drops (Railway cuts long runs), the backend
// finishes the extraction and saves the project itself — the browser only polls
// for it and navigates. That project never passes through createProject, so the
// project page has to do the fill, and it needs to know this is a fresh
// extraction rather than an old project being opened.
//
// sessionStorage, not localStorage: the marker must survive a reload (it does)
// and must NOT outlive the tab, so a stale flag can never fire a fill months
// later. Idempotency across reloads is still owned by the project blob's
// `_kainynas_auto_applied` stamp — this only says "a fill is expected".
const PRICE_FILL_PENDING_PREFIX = 'samatu_kainynas_pending:';

export function markPriceFillPending(projectId) {
  if (!projectId) return;
  try { sessionStorage.setItem(PRICE_FILL_PENDING_PREFIX + projectId, '1'); }
  catch { /* private mode / quota — the manual button still exists */ }
}

/**
 * Is a fill still expected for this project? Read-only.
 *
 * The consume-first version burned the marker before the fill had reached the
 * server: when the PUT was refused (409 lost-update guard), the prices lived
 * only in this browser's cache, the next backend pull replaced that cache, and
 * nothing was left to say a fill was ever owed. Peek, fill, and clear the marker
 * only once the server has taken the write. (2026-09-02)
 */
export function peekPriceFillPending(projectId) {
  if (!projectId) return false;
  try {
    return sessionStorage.getItem(PRICE_FILL_PENDING_PREFIX + projectId) === '1';
  } catch {
    return false;
  }
}

/** Read-and-clear. Returns true when this project was waiting for a fill. */
export function consumePriceFillPending(projectId) {
  if (!projectId) return false;
  try {
    const key = PRICE_FILL_PENDING_PREFIX + projectId;
    const pending = sessionStorage.getItem(key) === '1';
    if (pending) sessionStorage.removeItem(key);
    return pending;
  } catch {
    return false;
  }
}

// ── Settings ──────────────────────────────────────────────────────────────────

export function getSettings() {
  try {
    return JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');
  } catch {
    return {};
  }
}

export function saveSettings(settings) {
  _persist(SETTINGS_KEY, JSON.stringify(settings));
  return settings;
}

// ── Sprint §13 (2026-04-29): backup / restore localStorage projects ───────────
// Purpose: users will lose all projects if they clear browser history. The
// backend is the source of truth, but the local cache holds offline data
// (e.g. uncommitted price edits) the backend hasn't yet seen. Export gives
// the user a portable JSON they can re-import on a fresh browser.

// v2 (2026-07-28 audit): the backup carried projects + settings only, so a
// "Atsarginė kopija" taken before a browser wipe silently lost the user's PRICE
// LISTS — the thing they spent the most manual work on. They are in the payload
// now. Restoring a v1 backup still works: price_lists is simply absent.
// (2026-09-02: price lists ALSO have a backend mirror now, so the backup is
// belt-and-braces rather than the only copy — but a restore still pushes them
// back to the server, see importProjectsBackup.)
const BACKUP_VERSION = 2;

export function exportProjectsBackup() {
  const projects = getProjects();
  const settings = getSettings();
  const payload = {
    version: BACKUP_VERSION,
    exported_at: new Date().toISOString(),
    projects_count: projects.length,
    projects,
    settings,
    // Settings are still localStorage-only; price lists are mirrored server-side
    // since 2026-09-02 but stay in the payload so a v2 file remains complete.
    price_lists: getPriceLists(),
  };
  return JSON.stringify(payload, null, 2);
}

export function downloadProjectsBackup() {
  const json = exportProjectsBackup();
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const today = new Date().toISOString().slice(0, 10);
  const a = document.createElement('a');
  a.href = url;
  a.download = `samatu-projektai-${today}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function importProjectsBackup(jsonText, opts = {}) {
  // opts: { mergeStrategy: 'replace' | 'merge' (default) }
  const merge = opts.mergeStrategy !== 'replace';
  let parsed;
  try {
    parsed = JSON.parse(jsonText);
  } catch (e) {
    throw new Error(`Negaliu nuskaityti backup'o: failas neturi tinkamo JSON formato (${e.message})`);
  }
  if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.projects)) {
    throw new Error('Failas neatitinka backup struktūros (laukiamas { version, projects: [], settings })');
  }
  if (parsed.version > BACKUP_VERSION) {
    throw new Error(`Backup'as iš naujesnės versijos (${parsed.version}). Atnaujink Pathon ir bandyk vėl.`);
  }
  // Sprint §AUDIT (2026-04-29): explicit version migration table. Old
  // backups silently succeeded; now we apply known migrations + warn user
  // when format unknown. Each migration runs IN ORDER from incoming.version.
  const incomingVersion = Number(parsed.version) || 1;
  if (incomingVersion < BACKUP_VERSION) {
    // Apply migrations in sequence. Registered migrations:
    //   v1 → v2 : `price_lists` added to the payload. Nothing to transform —
    //             a v1 file simply has none, and the import below skips the
    //             restore when the key is absent (it must NOT wipe the price
    //             lists the browser already holds).
    for (let v = incomingVersion; v < BACKUP_VERSION; v++) {
      if (v === 1) parsed.price_lists = parsed.price_lists ?? null;
    }
    console.info(`[backup] migrating from v${incomingVersion} to v${BACKUP_VERSION}`);
  }
  // Run modern migrations on each project (skyrius normalize, etc.)
  parsed.projects = parsed.projects.map(_migrateProject);

  const incoming = parsed.projects;
  let final;
  if (merge) {
    const existing = getProjects();
    const byId = new Map(existing.map(p => [p.id, p]));
    for (const p of incoming) {
      if (!p?.id) continue;
      // Newer updated_at wins (or incoming if no timestamps)
      const old = byId.get(p.id);
      if (!old || (p.updated_at && (!old.updated_at || p.updated_at > old.updated_at))) {
        byId.set(p.id, p);
      }
    }
    final = Array.from(byId.values());
  } else {
    final = incoming;
  }
  // Wholesale cache replacement — same as the backend pull, so any debounced
  // save is flushed and the pending state cleared before the swap.
  flushProjectSaves();
  _replaceAll(final);

  if (parsed.settings && typeof parsed.settings === 'object') {
    saveSettings({ ...getSettings(), ...parsed.settings });
  }

  // Price lists (v2+). Merged by id, newest-file-wins per entry, so importing a
  // backup on a browser that already has lists never deletes one. `null`/absent
  // (a v1 backup) leaves the existing lists completely alone.
  let priceListsImported = 0;
  if (Array.isArray(parsed.price_lists)) {
    const byId = new Map(getPriceLists().map(pl => [pl.id, pl]));
    const restored = [];
    for (const pl of parsed.price_lists) {
      if (!pl?.id) continue;
      byId.set(pl.id, pl);
      restored.push(pl);
      priceListsImported += 1;
    }
    _persist(PRICE_LISTS_KEY, JSON.stringify(Array.from(byId.values())));
    // Push them to the backend too (2026-09-02): a restore that only refilled
    // localStorage would leave the durable copy missing the very lists the user
    // just recovered, and the next pull would delete them again.
    for (const pl of restored) _priceListsSyncToBackend(pl);
  }

  return {
    projects_imported: incoming.length,
    projects_total: final.length,
    settings_imported: !!parsed.settings,
    price_lists_imported: priceListsImported,
  };
}
