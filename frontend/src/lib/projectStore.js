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

const PROJECTS_KEY = 'samatu_projects';
const PRICE_LISTS_KEY = 'samatu_price_lists';
const SETTINGS_KEY = 'samatu_settings';

const API = '';

// P7: Legacy ASCII-stripped skyrius names → modern LT-with-diacritics. Used
// to migrate old projects in localStorage so UI shows consistent names.
// Mirror of backend SKYRIUS_LEGACY_MIGRATION (extractor/vision_call.py).
// Sprint §FIX-2 (2026-04-29): expanded with GKP/glaistymas variants —
// user reported 3 separate "GKP montavimas" groups in UI from these.
// Mirror of backend SKYRIUS_LEGACY_MIGRATION (extractor/vision_call.py).
const SKYRIUS_LEGACY_MIGRATION = {
  'Glaistymas dazymas': 'Sienų lubų glaistymas dažymas',
  'Glaistymas dažymas': 'Sienų lubų glaistymas dažymas',
  'Sienų glaistymas dažymas': 'Sienų lubų glaistymas dažymas',
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

function _migrateProject(p) {
  if (!p || typeof p !== 'object') return p;
  const migrated = { ...p };
  // Migrate skyrius names in darbu_sarasas
  if (Array.isArray(p.darbu_sarasas)) {
    migrated.darbu_sarasas = p.darbu_sarasas.map(it => {
      if (!it || typeof it !== 'object') return it;
      const newSk = SKYRIUS_LEGACY_MIGRATION[it.skyrius];
      const newSkLabel = SKYRIUS_LEGACY_MIGRATION[it.skyrius_label];
      if (newSk || newSkLabel) {
        return {
          ...it,
          skyrius: newSk || it.skyrius,
          skyrius_label: newSkLabel || it.skyrius_label,
        };
      }
      return it;
    });
  }
  // Same for pozicijos
  if (Array.isArray(p.pozicijos)) {
    migrated.pozicijos = p.pozicijos.map(it => {
      if (!it || typeof it !== 'object') return it;
      const newSk = SKYRIUS_LEGACY_MIGRATION[it.skyrius];
      return newSk ? { ...it, skyrius: newSk } : it;
    });
  }
  return migrated;
}

// ── Backend sync helpers (fire-and-forget) ────────────────────────────────────

const _syncToBackend = (project) => {
  if (!project?.id) return;
  // Sprint §AUDIT (2026-04-29): strip frontend-only meta keys before sync so
  // backend never persists _archived/_archived_at — they're frontend soft-delete
  // state. If they accidentally synced, restoreProject + page refresh wouldn't
  // stick because backend would override the restored state on next pull.
  const { _archived, _archived_at, ...persisted } = project;
  fetch(`${API}/api/projects/${project.id}`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(persisted),
  }).catch((e) => console.warn('[projectStore] backend sync failed:', e));
};

const _deleteFromBackend = (id) => {
  fetch(`${API}/api/projects/${id}`, { method: 'DELETE', credentials: 'include' })
    .catch((e) => console.warn('[projectStore] backend delete failed:', e));
};

// ── One-way pull (backend → localStorage) on app load ─────────────────────────
// Called from useProjectsSync hook below. Refreshes localStorage from backend
// to handle: (a) cross-device, (b) localStorage cleared, (c) project edited
// from another tab/session.

let _hasPulled = false;
// Sprint §AUDIT (2026-04-29): exported reset so authContext.logout() can
// clear the once-per-session guard. Without this, user A's archived flag
// would carry into user B's session in the same tab.
export function resetPullCache() {
  _hasPulled = false;
}
export async function pullProjectsFromBackend({ force = false } = {}) {
  if (_hasPulled && !force) return null;
  _hasPulled = true;
  try {
    const res = await fetch(`${API}/api/projects`, { credentials: 'include' });
    if (res.status === 401) {
      // Not authenticated — caller (AuthProvider) handles redirect; clear cache.
      localStorage.removeItem(PROJECTS_KEY);
      return null;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { projects: list = [] } = await res.json();

    // Backend is source of truth — replace cache fully (don't merge old localStorage
    // entries from a previous user/session; we cleared on logout but this is defensive).
    // Sprint §FIX (2026-04-29): preserve local archive state across pulls.
    // _archived is frontend-only soft-delete flag; backend doesn't know about
    // it, so a naïve overwrite would resurrect deleted projects on every refresh.
    let archiveMap = {};
    try {
      const localList = JSON.parse(localStorage.getItem(PROJECTS_KEY) || '[]');
      for (const p of localList) {
        if (p?._archived && p.id) {
          archiveMap[p.id] = {
            _archived: p._archived,
            _archived_at: p._archived_at,
          };
        }
      }
    } catch { /* ignore */ }

    if (list.length === 0) {
      // Even if backend returns empty, keep the archived projects locally
      // so user can still see/restore them from Šiukšliadėžė.
      const archivedOnly = Object.entries(archiveMap).map(([id, a]) => ({ id, ...a }));
      localStorage.setItem(PROJECTS_KEY, JSON.stringify(archivedOnly));
      return archivedOnly;
    }

    // Backend returns SUMMARIES — fetch full data per project.
    const fulls = await Promise.all(
      list.map(p => fetch(`${API}/api/projects/${p.id}`, { credentials: 'include' })
                     .then(r => r.ok ? r.json() : null))
    );
    const valid = fulls.filter(Boolean).map(p => ({
      ...p,
      ...(archiveMap[p.id] || {}),  // restore _archived/_archived_at if present
    })).sort((a, b) =>
      (b.updated_at || b.created_date || '').localeCompare(a.updated_at || a.created_date || '')
    );
    localStorage.setItem(PROJECTS_KEY, JSON.stringify(valid));
    return valid;
  } catch (e) {
    console.warn('[projectStore] pull from backend failed:', e);
    return null;
  }
}

// ── Projects CRUD (sync API, async backend write-through) ─────────────────────

export function getProjects() {
  try {
    const raw = JSON.parse(localStorage.getItem(PROJECTS_KEY) || '[]');
    // P7 migration: legacy skyrius mojibake → modern LT names. Pure-function
    // pass — doesn't write back, so old saves stay untouched until next save.
    return raw.map(_migrateProject);
  } catch {
    return [];
  }
}

export function getProject(id) {
  return getProjects().find(p => p.id === id) || null;
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
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));
  _syncToBackend(project);
  return project;
}

export function updateProject(id, updates) {
  const projects = getProjects();
  const idx = projects.findIndex(p => p.id === id);
  if (idx < 0) return null;
  projects[idx] = { ...projects[idx], ...updates, updated_at: new Date().toISOString() };
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));
  _syncToBackend(projects[idx]);
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
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(all));
  // Don't delete from backend yet — preserved until purge window expires.
}

export function restoreProject(id) {
  const all = getProjects();
  const target = all.find(p => p.id === id);
  if (!target) return;
  delete target._archived;
  delete target._archived_at;
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(all));
}

export function permanentlyDeleteProject(id) {
  const projects = getProjects().filter(p => p.id !== id);
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));
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

// ── Correction audit log (Phase 12.3 learning loop foundation) ────────────────

export function logCorrection(projectId, payload) {
  if (!projectId || !payload?.field_path) return;
  fetch(`${API}/api/projects/${projectId}/corrections`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).catch((e) => console.warn('[projectStore] correction log failed:', e));
}

// ── Price Lists (still localStorage-only — low value to sync for MVP) ─────────

export function getPriceLists() {
  try {
    return JSON.parse(localStorage.getItem(PRICE_LISTS_KEY) || '[]');
  } catch {
    return [];
  }
}

export function createPriceList(data) {
  const pl = {
    ...data,
    id: crypto.randomUUID(),
    created_date: new Date().toISOString(),
  };
  const lists = getPriceLists();
  lists.unshift(pl);
  localStorage.setItem(PRICE_LISTS_KEY, JSON.stringify(lists));
  return pl;
}

export function deletePriceList(id) {
  const lists = getPriceLists().filter(p => p.id !== id);
  localStorage.setItem(PRICE_LISTS_KEY, JSON.stringify(lists));
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
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  return settings;
}

// ── Sprint §13 (2026-04-29): backup / restore localStorage projects ───────────
// Purpose: users will lose all projects if they clear browser history. The
// backend is the source of truth, but the local cache holds offline data
// (e.g. uncommitted price edits) the backend hasn't yet seen. Export gives
// the user a portable JSON they can re-import on a fresh browser.

const BACKUP_VERSION = 1;

export function exportProjectsBackup() {
  const projects = getProjects();
  const settings = getSettings();
  const payload = {
    version: BACKUP_VERSION,
    exported_at: new Date().toISOString(),
    projects_count: projects.length,
    projects,
    settings,
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
    throw new Error(`Backup'as iš naujesnės versijos (${parsed.version}). Atnaujink Sąmatų AI ir bandyk vėl.`);
  }
  // Sprint §AUDIT (2026-04-29): explicit version migration table. Old
  // backups silently succeeded; now we apply known migrations + warn user
  // when format unknown. Each migration runs IN ORDER from incoming.version.
  const incomingVersion = Number(parsed.version) || 1;
  if (incomingVersion < BACKUP_VERSION) {
    // Apply migrations in sequence. v1 → v2 example:
    // for (let v = incomingVersion; v < BACKUP_VERSION; v++) {
    //   if (v === 1) parsed.projects = migrateV1ToV2(parsed.projects);
    // }
    // For now BACKUP_VERSION = 1 so no migrations needed; this block is
    // scaffolding for when we bump.
    console.info(`[backup] migrating from v${incomingVersion} to v${BACKUP_VERSION} (no migrations registered yet)`);
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
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(final));

  if (parsed.settings && typeof parsed.settings === 'object') {
    saveSettings({ ...getSettings(), ...parsed.settings });
  }

  return {
    projects_imported: incoming.length,
    projects_total: final.length,
    settings_imported: !!parsed.settings,
  };
}
