import { DEMO_PROJECTS } from '../demoData';

/**
 * projectStore — durable project storage.
 *
 * Architecture (Phase 12.3):
 * - Write-through: every mutation writes to localStorage (instant UX) AND
 *   POSTs to backend /api/projects (durable, cross-device).
 * - Backend is the source of truth; localStorage is the offline cache.
 * - On first app load (after schema migration or fresh device), localStorage
 *   is empty; we fetch backend list and populate localStorage as cache.
 *
 * Backend POSTs are fire-and-forget — UI never blocks waiting for them.
 * If backend is offline, localStorage still works; sync resumes when online.
 */

const PROJECTS_KEY = 'samatu_projects';
const PRICE_LISTS_KEY = 'samatu_price_lists';
const SETTINGS_KEY = 'samatu_settings';

const API = '';

// Seed demo data on first load (empty localStorage)
if (!localStorage.getItem(PROJECTS_KEY)) {
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(DEMO_PROJECTS));
}

// ── Backend sync helpers (fire-and-forget) ────────────────────────────────────

const _syncToBackend = (project) => {
  if (!project?.id) return;
  fetch(`${API}/api/projects/${project.id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(project),
  }).catch((e) => console.warn('[projectStore] backend sync failed:', e));
};

const _deleteFromBackend = (id) => {
  fetch(`${API}/api/projects/${id}`, { method: 'DELETE' })
    .catch((e) => console.warn('[projectStore] backend delete failed:', e));
};

// ── One-way pull (backend → localStorage) on app load ─────────────────────────
// Called from useProjectsSync hook below. Refreshes localStorage from backend
// to handle: (a) cross-device, (b) localStorage cleared, (c) project edited
// from another tab/session.

let _hasPulled = false;
export async function pullProjectsFromBackend({ force = false } = {}) {
  if (_hasPulled && !force) return null;
  _hasPulled = true;
  try {
    const res = await fetch(`${API}/api/projects`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { projects: list = [] } = await res.json();
    if (list.length === 0) return null;

    // Backend returns SUMMARIES — to populate cache fully, fetch each.
    // For 100+ projects, this is a lot of round trips — acceptable for MVP.
    const fulls = await Promise.all(
      list.map(p => fetch(`${API}/api/projects/${p.id}`).then(r => r.ok ? r.json() : null))
    );
    const valid = fulls.filter(Boolean);

    // Merge with localStorage by updated_at — keep newer
    const local = JSON.parse(localStorage.getItem(PROJECTS_KEY) || '[]');
    const byId = new Map(local.map(p => [p.id, p]));
    for (const p of valid) {
      const existing = byId.get(p.id);
      if (!existing || (p.updated_at && existing.updated_at && p.updated_at > existing.updated_at)) {
        byId.set(p.id, p);
      }
    }
    const merged = Array.from(byId.values()).sort((a, b) =>
      (b.updated_at || b.created_date || '').localeCompare(a.updated_at || a.created_date || '')
    );
    localStorage.setItem(PROJECTS_KEY, JSON.stringify(merged));
    return merged;
  } catch (e) {
    console.warn('[projectStore] pull from backend failed:', e);
    return null;
  }
}

// ── Projects CRUD (sync API, async backend write-through) ─────────────────────

export function getProjects() {
  try {
    return JSON.parse(localStorage.getItem(PROJECTS_KEY) || '[]');
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

export function deleteProject(id) {
  const projects = getProjects().filter(p => p.id !== id);
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));
  _deleteFromBackend(id);
}

// ── Correction audit log (Phase 12.3 learning loop foundation) ────────────────

export function logCorrection(projectId, payload) {
  if (!projectId || !payload?.field_path) return;
  fetch(`${API}/api/projects/${projectId}/corrections`, {
    method: 'POST',
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
