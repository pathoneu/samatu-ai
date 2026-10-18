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
import { learningEventsFromChange } from './learningEvents.js';

const PROJECTS_KEY = 'samatu_projects';
const PRICE_LISTS_KEY = 'samatu_price_lists';
const SETTINGS_KEY = 'samatu_settings';
// Which account the cached projects and price lists were written for
// (2026-09-30) — set whenever a session begins, see claimLocalCache().
const CACHE_OWNER_KEY = 'samatu_cache_owner';

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
// Persisted (2026-09-15 review): in memory only, the first PUT after a page
// load carried no base at all and the backend skipped its 409 check — the
// lost-update guard silently switched itself off on every reload.
const VERSIONS_KEY = 'samatu_server_versions';
function _loadVersions() {
  try {
    const raw = globalThis.localStorage?.getItem(VERSIONS_KEY);
    const obj = raw ? JSON.parse(raw) : null;
    return new Map(obj && typeof obj === 'object' ? Object.entries(obj) : []);
  } catch {
    return new Map();
  }
}
const _serverVersions = _loadVersions();
function _saveVersions() {
  try { globalThis.localStorage?.setItem(VERSIONS_KEY, JSON.stringify(Object.fromEntries(_serverVersions))); } catch { /* private window, quota */ }
}
function _setServerVersion(id, updatedAt) {
  if (!id || !updatedAt) return;
  _serverVersions.set(id, updatedAt);
  _saveVersions();
}

export function _getServerVersion(id) {   // test hook
  return _serverVersions.get(id);
}

// Adopt a server-side version stamp produced OUTSIDE the PUT path — e.g. the
// revalidate endpoint persists on the server and returns the new updated_at.
// Without re-basing here, the tab's next write-through carries a stale
// base_updated_at, trips the 409 guard below and falsely reports lost work.
export function noteServerVersion(id, updatedAt) {
  _setServerVersion(id, updatedAt);
}

// At most ONE PUT on the wire per project id, plus the newest snapshot waiting
// behind it. (2026-09-29 audit) A new save used to ABORT the PUT still in
// flight — but the server had often stored that request already, so its
// updated_at moved on while this tab never saw the answer and kept the old base:
// the next PUT came back 409, and so did every save after it in the tab. Now
// nothing is aborted. While a PUT is on the wire only the LATEST snapshot is
// remembered, and it goes out when that PUT settles, carrying the version the
// answer just reported. Requests for one project thus reach the server strictly
// one after another, so the user's last change is the last one it stores.
const _inflight = new Map();   // id -> { done: Promise } for the PUT on the wire
const _queued = new Map();     // id -> { project, opts, promise, resolve }

const _syncToBackend = (project, opts = {}) => {
  if (!project?.id) return;
  const id = project.id;
  if (!_inflight.has(id)) return _sendPut(project, opts);
  const waiting = _queued.get(id);
  if (waiting) {
    // Replace the snapshot, keep one promise: every caller waiting on this
    // project learns the verdict of the PUT that actually carries its edit.
    waiting.project = project;
    waiting.opts = { ...waiting.opts, ...opts };
    return waiting.promise;
  }
  let resolve;
  const promise = new Promise((r) => { resolve = r; });
  _queued.set(id, { project, opts, promise, resolve });
  return promise;
};

function _sendPut(project, { keepArchiveFlags = false, versionSource = null } = {}) {
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
  const withBase = base ? { ...persisted, base_updated_at: base } : persisted;
  // What kind of save this is, for the project's version history (Istorija):
  // a protocol field the server pops, like base_updated_at.
  const body = versionSource ? { ...withBase, _versija_saltinis: versionSource } : withBase;

  // `token` is this PUT's slot. A user switch or a permanent delete drops the
  // slot, so a late answer is ignored — it is never aborted: the server may
  // already hold it.
  const token = {};
  _inflight.set(id, token);
  const mine = () => _inflight.get(id) === token;
  // The PUT is settled: free the slot and send the snapshot that waited.
  const settle = (verdict) => {
    _inflight.delete(id);
    const next = _queued.get(id);
    if (next) {
      _queued.delete(id);
      next.resolve(_sendPut(next.project, next.opts));
    }
    return verdict;
  };

  // `new Promise(… fetch …)` calls fetch synchronously but turns a synchronous
  // throw into a rejection, so the slot is always freed.
  token.done = new Promise((ok) => ok(fetch(`${API}/api/projects/${id}`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }))).then(async (res) => {
    if (!mine()) return 'superseded';
    const verdict = _handleSyncResponse(res);
    if (verdict === 'ok') {
      // Track what the server now holds so the NEXT save carries a fresh base.
      try {
        const saved = await res.json();
        if (saved?.updated_at && mine()) _setServerVersion(id, saved.updated_at);
      } catch { /* body not JSON — leave the old base, worst case a false 409 */ }
    }
    return mine() ? settle(verdict) : 'superseded';
  }).catch((e) => {
    if (!mine()) return 'superseded';
    _handleSyncError(e);
    return settle('failed');
  });
  return token.done;
}

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
    if (opts) _pendingOpts.set(id, { ..._pendingOpts.get(id), ...opts });
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
 * @returns {Promise<Array<{id: string, verdict: string}>>} one entry per
 *   project this flush pushed ('ok' | 'conflict' | 'unauthorized' | 'failed' |
 *   'superseded' — the last only after a user switch or a permanent delete);
 *   a snapshot that waits behind a PUT already on the wire resolves once its
 *   own PUT is answered. Empty when there was nothing pending.
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
  // PUTs still on the wire are NOT aborted (the server may already hold them);
  // dropping their slots makes their late answers change nothing here.
  _inflight.clear();
  for (const q of _queued.values()) q.resolve('superseded');
  _queued.clear();
  _serverVersions.clear();
  _saveVersions();
  _refreshedFromServer.clear();
  // Price lists are user-scoped and backend-backed since 2026-09-02 — releasing
  // their once-per-session guard here is what makes the NEXT user's first
  // Kainynai visit fetch his own lists instead of reusing the previous pull.
  // (authContext.purgeLocalUserData already drops the cached rows themselves.)
  _hasPulledPriceLists = false;
  // Company details (2026-09-29): a pull still on the wire for the previous
  // account must not land in the next one's cache — the new epoch drops it.
  _settingsEpoch += 1;
  _settingsPull = null;
  _settingsWrite = null;
  _settingsUserId = null;
}

/**
 * Called whenever a session begins (2026-09-30). Login and register purge the
 * cache themselves; a Google sign-in finishes through a server redirect, so the
 * app only learns of that session when it restores it on page load — and the
 * previous account's projects, company details and price lists were still
 * here. This compares the signed-in account with the owner recorded for the
 * cache and purges a foreign cache BEFORE anything reads it:
 *
 *   · an owner marker for another account               → purge everything
 *   · a sign-in just happened (signIn) and some cached
 *     data carries no owner marker                        → purge everything
 *   · a plain reload, no marker yet (a cache from before
 *     the marker existed)                                 → drop the projects and
 *     price lists (the server copy comes back on the next pull); keep the
 *     company details, which may still exist only here and wait for the
 *     one-time carry-over in _pullSettings
 *
 * Then records the account as the cache's owner. Returns true when it purged.
 */
export function claimLocalCache(userId, { signIn = false } = {}) {
  if (!userId) return false;
  const id = String(userId);
  const read = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
  const drop = (k) => { try { localStorage.removeItem(k); } catch { /* ignore */ } };
  const cacheOwner = read(CACHE_OWNER_KEY);
  const settingsOwner = read(SETTINGS_OWNER_KEY);
  const otherOwner = [cacheOwner, settingsOwner].some((o) => o && o !== id);
  const unmarkedLists = !cacheOwner && (read(PROJECTS_KEY) !== null || read(PRICE_LISTS_KEY) !== null);
  const unmarkedSettings = !settingsOwner && read(SETTINGS_KEY) !== null;
  const purge = otherOwner || (signIn && (unmarkedLists || unmarkedSettings));
  if (purge) {
    for (const k of [PROJECTS_KEY, SETTINGS_KEY, PRICE_LISTS_KEY, SETTINGS_OWNER_KEY]) drop(k);
    resetPullCache();
  } else if (unmarkedLists) {
    drop(PROJECTS_KEY);
    drop(PRICE_LISTS_KEY);
    resetPullCache();
  }
  _persist(CACHE_OWNER_KEY, id);
  return purge;
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
      if (p?.id && p.updated_at) _setServerVersion(p.id, p.updated_at);
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

// ── One project, fresh from the server ────────────────────────────────────────
// The cached copy can be OLDER than the server's blob — a backfill, a save from
// another browser or device — while the room sheet's facts are computed
// server-side from the current blob. So the sheet showed a perimeter the cached
// rooms did not carry, and the first save after a page load, which has no base
// version to check against, pushed the stale rooms over it (2026-09-10, a scope
// toggle on a backfilled project). Pages that edit a project call this on
// mount: the cached entry is replaced when the server's is newer and has no
// unsaved local edit, and the server version is recorded for the conflict
// check either way. Resolves to the project now in the cache (null when neither
// side has it).
export async function refreshProjectFromBackend(id) {
  if (!id) return null;
  let fresh;
  try {
    const r = await fetch(`${API}/api/projects/${id}`, { credentials: 'include' });
    if (!r.ok) return getProject(id);
    fresh = await r.json();
  } catch {
    return getProject(id);
  }
  if (!fresh || fresh.id !== id) return getProject(id);
  // An unsaved local edit is pushed first, then compared — and its base stays
  // the version it was made on. Rebasing here (2026-09-13 – 09-15) handed the
  // pending PUT the server's NEWER stamp, so a stale cache plus one edit
  // overwrote another device's work with no 409.
  // A snapshot waiting behind a PUT on the wire is an unsaved edit too.
  if (_dirtyIds.has(id) || _queued.has(id)) return getProject(id);
  const raw = _readProjectsRaw();
  const projects = Array.isArray(raw) ? raw : [];
  const cached = projects.find(p => p?.id === id) || null;
  // The server MOVED ON since this browser last saw it (Pathon v3 W1-F F4): its stamp is not the one this
  // browser last saved or loaded — another tab or device saved, a version was restored elsewhere, a database
  // was put back. Compared server stamp to server stamp: `cached.updated_at` is THIS browser's clock
  // (updateProject stamps it), so a PC clock a few minutes fast — or a restore that put an older stamp
  // back — kept the stale cached copy on screen. The next save would only have 409'd against it anyway.
  const seen = _serverVersions.get(id);
  const moved = !!cached && !!seen && !!fresh.updated_at && fresh.updated_at !== seen;
  const newer = !cached || !cached.updated_at || moved
    || (!!fresh.updated_at && fresh.updated_at > cached.updated_at);
  if (!newer) return getProject(id);   // a conflicted local copy keeps its old base → the next save 409s again
  if (fresh.updated_at) _setServerVersion(id, fresh.updated_at);
  const next = cached ? projects.map(p => (p?.id === id ? fresh : p)) : [fresh, ...projects];
  _memProjects = next;
  // a refused localStorage write leaves the flag set, so the next flush retries it
  _lsDirty = !_persist(PROJECTS_KEY, JSON.stringify(next));
  // What he sees changed under him: the workspace says „Atnaujinta iš serverio" once. Its own save whose
  // answer never came back (a tab closed with the PUT on the wire) holds the same content — nothing to say.
  if (moved && !_sameContent(cached, fresh)) {
    _refreshedFromServer.add(id);
    try { globalThis.dispatchEvent?.(new CustomEvent(SERVER_REFRESH_EVENT, { detail: { id } })); } catch { /* no DOM */ }
  }
  return getProject(id);
}

// ── „Atnaujinta iš serverio" (Pathon v3 W1-F F4) ─────────────────────────────
// Projects whose cached copy a load replaced because the server moved on and the content differs. The
// workspace shows one notice per project until it is dismissed (components/project/ServerRefreshNotice).
export const SERVER_REFRESH_EVENT = 'samatu:project-refreshed-from-server';
const _refreshedFromServer = new Set();
export function hasServerRefreshNotice(id) { return _refreshedFromServer.has(id); }
export function dismissServerRefreshNotice(id) { _refreshedFromServer.delete(id); }

// Keys the server sets on the row (db.get_project lays them over the blob) or a save adds as protocol —
// never what he changed.
const _ROW_KEYS = new Set([
  'updated_at', 'created_at', 'user_id', 'share_token', 'share_expires_at', 'share_view_count',
  'share_last_viewed_at', 'status', 'vat_rate', 'tipas', 'archetipas', 'bendras_plotas_m2',
  'base_updated_at', '_versija_saltinis', '_archived', '_archived_at',
]);
function _canon(v) {
  if (Array.isArray(v)) return `[${v.map(_canon).join(',')}]`;
  if (v && typeof v === 'object') {
    return `{${Object.keys(v).filter((k) => v[k] !== undefined).sort()
      .map((k) => `${JSON.stringify(k)}:${_canon(v[k])}`).join(',')}}`;
  }
  return JSON.stringify(v) ?? 'null';
}
function _sameContent(a, b) {
  for (const k of new Set([...Object.keys(a || {}), ...Object.keys(b || {})])) {
    if (!_ROW_KEYS.has(k) && _canon(a?.[k]) !== _canon(b?.[k])) return false;
  }
  return true;
}

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

/**
 * @param {{versionSource?: string}} [opts] — `versionSource` names the save in
 *   the project's history ('perskaityta' | 'lapas' | 'klausimas' …; default
 *   'issaugota' on the server). It rides the debounced PUT that carries this edit.
 */
export function updateProject(id, updates, opts) {
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
  const before = projects[idx];
  projects[idx] = { ...projects[idx], ...updates, updated_at: new Date().toISOString() };
  // THE hot path — debounced. Everything else in this module saves immediately.
  _scheduleSave(projects, id, opts?.versionSource ? { versionSource: opts.versionSource } : undefined);
  // The learning journal (togal-v2 W11): every surface saves through here, so a row „Teisinga", a typed
  // quantity or a room „patvirtinta" is recorded whichever table or rail it was made in.
  for (const payload of learningEventsFromChange(before, projects[idx])) logCorrection(id, payload);
  return projects[idx];
}

/**
 * Take a project the SERVER has just written (a version restore) as the cached
 * one, and its updated_at as the base for the next save — without a PUT. The
 * caller flushes pending saves first; without re-basing, this tab's next save
 * would 409 against its own restore.
 */
export function adoptServerProject(project) {
  if (!project?.id) return null;
  const id = project.id;
  _dirtyIds.delete(id);
  _pendingOpts.delete(id);
  if (project.updated_at) _setServerVersion(id, project.updated_at);
  const raw = _readProjectsRaw();
  const projects = Array.isArray(raw) ? raw : [];
  const next = projects.some((p) => p?.id === id)
    ? projects.map((p) => (p?.id === id ? project : p))
    : [project, ...projects];
  _memProjects = next;
  _lsDirty = !_persist(PROJECTS_KEY, JSON.stringify(next));
  return getProject(id);
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
  // Drop any pending or waiting PUT for this id — a save that landed AFTER the
  // DELETE would resurrect the project server-side. A PUT already on the wire
  // is not aborted (the server may have it); the DELETE waits for its answer
  // instead, so it is always the last word.
  _dirtyIds.delete(id);
  _pendingOpts.delete(id);
  const waiting = _queued.get(id);
  if (waiting) { waiting.resolve('superseded'); _queued.delete(id); }
  const onWire = _inflight.get(id)?.done;
  _inflight.delete(id);              // its late answer must not re-record a version
  _serverVersions.delete(id);
  _saveVersions();
  _saveNow(projects, null);
  if (onWire) onWire.then(() => _deleteFromBackend(id));
  else _deleteFromBackend(id);
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

/** Fired on `window` after a correction row is stored: `{projectId, source}`. */
export const LEARNING_EVENT = 'samatu:learning-logged';

export function logCorrection(projectId, payload) {
  if (!projectId || !payload?.field_path) return Promise.resolve(false);
  return fetch(`${API}/api/projects/${projectId}/corrections`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
    .then((res) => {
      // „Įsiminta" and the journal re-read the log when a row lands
      if (res.ok && typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent(LEARNING_EVENT, { detail: { projectId, source: payload.source } }));
      }
      return res.ok;
    })
    .catch((e) => {
      console.warn('[projectStore] correction log failed:', e);
      return false;
    });
}

/** The project's correction corpus as a CSV download (togal-v2 W11): laikas, patalpa, laukas, buvo, tapo, saltinis, pastaba. */
export function correctionsCsvUrl(projectId) {
  return projectId ? `${API}/api/projects/${encodeURIComponent(projectId)}/corrections.csv` : null;
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

// ── Settings (company details + logo) ─────────────────────────────────────────
//
// SERVER-BACKED since 2026-09-29 (audit frontend-architecture-3). authContext
// purges `samatu_settings` at every login and logout on purpose — the next
// person on a shared browser must not inherit another company's IBAN — and that
// purge used to delete the ONLY copy, so every re-login silently took the logo,
// IBAN and codes out of his exports. GET/PUT /api/settings is now the durable
// copy; localStorage stays the synchronous cache the pages and exports read.
//
// SETTINGS_OWNER_KEY says which account the cache was written for, so the
// one-time carry-over (details that exist only in this browser go up once) can
// never hand one account's details to another.
const SETTINGS_OWNER_KEY = 'samatu_settings_owner';
let _settingsUserId = null;  // the signed-in account this cache serves
let _settingsEpoch = 0;      // bumped on every user switch (resetPullCache)
let _settingsRev = 0;        // bumped on every local save
let _settingsPull = null;    // this session's pull; null = not started / failed
let _settingsWrite = null;   // the last PUT → 'ok' | 'failed' | 'other_account'

export function getSettings() {
  try {
    return JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');
  } catch {
    return {};
  }
}

/**
 * Write the cache at once and send the whole object to the server. Returns the
 * settings synchronously, as before; `flushSettingsWrites()` says whether the
 * server took it. A failed send keeps the local copy.
 *
 * 2026-09-30: the save carries the account this page was loaded for, and the
 * server refuses it (409 → 'other_account') when the session now belongs to
 * someone else — a second tab left on A's Settings page after the first tab
 * signed B in. Such a tab also leaves the shared cache alone once it is marked
 * for another account, so B's exports never read A's details.
 */
export function saveSettings(settings) {
  const forUser = _settingsUserId;
  if (!_cacheIsOtherAccounts(forUser)) {
    _persist(SETTINGS_KEY, JSON.stringify(settings));
    if (forUser) _persist(SETTINGS_OWNER_KEY, forUser);
  }
  _settingsRev += 1;
  // One PUT at a time, in order — two quick saves must not land swapped.
  const prev = _settingsWrite || Promise.resolve();
  _settingsWrite = prev.then(() => _putSettings(settings, forUser));
  return settings;
}

function _cacheIsOtherAccounts(userId) {
  if (!userId) return false;
  let owner = null;
  try { owner = localStorage.getItem(CACHE_OWNER_KEY); } catch { /* ignore */ }
  return !!owner && owner !== String(userId);
}

async function _putSettings(settings, forUser) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (forUser) headers['X-Settings-For-User'] = String(forUser);
    const res = await fetch(`${API}/api/settings`, {
      method: 'PUT',
      credentials: 'include',
      headers,
      body: JSON.stringify(settings),
    });
    if (res?.ok) return 'ok';
    if (res?.status === 409) return 'other_account';
    console.warn('[projectStore] settings save refused:', res?.status);
  } catch (e) {
    console.warn('[projectStore] settings save failed:', e);
  }
  return 'failed';
}

/** 'ok' | 'failed' | 'other_account' for the last save; null when nothing was sent. */
export async function flushSettingsWrites() {
  return _settingsWrite ? _settingsWrite : null;
}

/**
 * Fill the cache from the server — once per session (login or session
 * restore), shared by every caller. A failed pull leaves the cache alone and
 * lets the next caller retry.
 */
export function pullSettingsFromBackend(userId) {
  if (_settingsPull && (!userId || userId === _settingsUserId)) return _settingsPull;
  if (userId) _settingsUserId = userId;
  const epoch = _settingsEpoch;
  const pull = _pullSettings(_settingsUserId, epoch, _settingsRev).then((got) => {
    if (got === null && epoch === _settingsEpoch && _settingsPull === pull) _settingsPull = null;
    return got;
  });
  _settingsPull = pull;
  return pull;
}

async function _pullSettings(userId, epoch, rev) {
  try {
    if (_settingsWrite) await _settingsWrite;      // a save on the wire lands first
    const res = await fetch(`${API}/api/settings`, { credentials: 'include' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const server = await res.json();
    if (!server || typeof server !== 'object' || Array.isArray(server)) {
      throw new Error('bad payload');
    }
    if (epoch !== _settingsEpoch) return null;     // another account signed in meanwhile
    if (rev !== _settingsRev) return getSettings(); // he saved meanwhile — his copy is newer
    const local = getSettings();
    let owner = null;
    try { owner = localStorage.getItem(SETTINGS_OWNER_KEY); } catch { /* ignore */ }
    if (!Object.keys(server).length && Object.keys(local).length) {
      // Account not known yet (a reader got here before authContext's pull):
      // leave the local copy for that pull to judge.
      if (!userId) return local;
      // One-time carry-over: the server has nothing yet, and this browser holds
      // details written for this same account (or before the owner mark existed).
      if (!owner || owner === userId) {
        saveSettings(local);
        return local;
      }
    }
    _persist(SETTINGS_KEY, JSON.stringify(server));
    if (userId) _persist(SETTINGS_OWNER_KEY, userId);
    return server;
  } catch (e) {
    console.warn('[projectStore] settings pull failed:', e);
    return null;
  }
}

/**
 * The exports and the Settings page await this before reading the cache: it
 * resolves once this session's pull has finished (starting one if none has).
 */
export async function ensureSettingsPulled() {
  await pullSettingsFromBackend();
  return getSettings();
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
    // Price lists (since 2026-09-02) and settings (since 2026-09-29) are
    // mirrored server-side but stay in the payload so a v2 file remains complete.
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

// What the server holds right now: id -> updated_at, or null when it could not
// be asked (offline, expired session, server error).
async function _fetchServerVersions() {
  try {
    const res = await fetch(`${API}/api/projects`, { credentials: 'include' });
    if (!res.ok) return null;
    const { projects: list } = await res.json();
    if (!Array.isArray(list)) return null;
    return new Map(list.filter(p => p?.id).map(p => [p.id, p.updated_at || null]));
  } catch {
    return null;
  }
}

/**
 * Restore a backup file: merge it into the cache AND send the restored projects
 * to the server. (2026-09-29 audit) It used to fill the cache only — the next
 * Dashboard pull replaces the cache with the server's list, so every restored
 * project the server did not have vanished without a word.
 *
 * A project whose server copy is NEWER than the file's is left as the server has
 * it (counted in `projects_kept_server`) — the file's older copy is not adopted
 * and not sent. Every other project in the file goes through the ordinary save
 * path: with the server's version as base when the server has the id, with no
 * base when it does not. `projects_saved` / `projects_failed` count what the
 * server actually took; when the server cannot be asked at all, nothing is sent
 * and every candidate counts as failed (it stays in this browser, as before).
 */
export async function importProjectsBackup(jsonText, opts = {}) {
  // opts: { mergeStrategy: 'replace' | 'merge' (default) }
  const merge = opts.mergeStrategy !== 'replace';
  let parsed;
  try {
    parsed = JSON.parse(jsonText);
  } catch {
    // Settings → „Atsarginė kopija" shows this as it is (2026-10-06: in his words — no format names)
    throw new Error('Šio failo perskaityti nepavyko — tai ne Pathon atsarginė kopija arba failas sugadintas.');
  }
  if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.projects)) {
    throw new Error('Šis failas nėra Pathon atsarginė kopija.');
  }
  if (parsed.version > BACKUP_VERSION) {
    throw new Error('Ši atsarginė kopija padaryta naujesne programos versija. Perkraukite puslapį ir bandykite dar kartą.');
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
  // The sample project is local-only — never sent, never compared.
  const toServer = incoming.filter(p => p?.id && !p.is_demo);
  const onServer = toServer.length ? await _fetchServerVersions() : new Map();
  const keptOnServer = new Set();
  for (const p of toServer) {
    const theirs = onServer?.get(p.id);
    if (theirs && !(p.updated_at && p.updated_at > theirs)) keptOnServer.add(p.id);
  }
  let final;
  if (merge) {
    const existing = getProjects();
    const byId = new Map(existing.map(p => [p.id, p]));
    for (const p of incoming) {
      if (!p?.id || keptOnServer.has(p.id)) continue;
      // Newer updated_at wins (or incoming if no timestamps)
      const old = byId.get(p.id);
      if (!old || (p.updated_at && (!old.updated_at || p.updated_at > old.updated_at))) {
        byId.set(p.id, p);
      }
    }
    final = Array.from(byId.values());
  } else {
    final = incoming.filter(p => !keptOnServer.has(p?.id));
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

  // Every file project the server lacks or holds older goes out through the
  // ordinary save path — the cache's copy after the merge, which is the file's
  // or a newer local one. Deciding by the SERVER (not by what the merge
  // changed) is what lets a second import of the same file retry a failed
  // send. The base is what the server holds NOW (none for an id it does not
  // have), so a copy that changes on the server meanwhile still meets the 409
  // guard. Archive flags go as restored, so an archived project stays archived.
  const pushIds = [...new Set(toServer.map(p => p.id))].filter(id => !keptOnServer.has(id));
  let projectsSaved = 0;
  let projectsFailed = 0;
  if (pushIds.length && !onServer) {
    projectsFailed = pushIds.length;
  } else if (pushIds.length) {
    for (const id of pushIds) {
      const theirs = onServer.get(id);
      if (theirs) _serverVersions.set(id, theirs);
      else _serverVersions.delete(id);
      _dirtyIds.add(id);
      _pendingOpts.set(id, { keepArchiveFlags: true });
    }
    _saveVersions();
    for (const { verdict } of await flushProjectSaves()) {
      if (verdict === 'ok') projectsSaved += 1;
      else projectsFailed += 1;
    }
  }

  return {
    projects_imported: incoming.length,
    projects_total: final.length,
    projects_saved: projectsSaved,
    projects_failed: projectsFailed,
    projects_kept_server: keptOnServer.size,
    settings_imported: !!parsed.settings,
    price_lists_imported: priceListsImported,
  };
}
