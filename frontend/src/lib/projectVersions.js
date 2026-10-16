/**
 * projectVersions.js — the project's saved versions (togal-v2 W10): what the „Istorija" drawer lists,
 * compares and restores.
 *
 * The server keeps every saved state of a project (backend/db.py, `project_versions`); this module only
 * talks to it (`/api/projects/{id}/versions…`) and words what comes back. Measurements and count marks
 * have their own, separate history in the viewer (lib/measureHistory.js — in memory, this tab only);
 * the drawer says so.
 */
import { API_BASE } from './apiBase.js';

/** Where a version came from, as he reads it. */
export const SOURCE_LABELS = Object.freeze({
  issaugota: 'Išsaugota',
  perskaityta: 'Brėžinys perskaitytas iš naujo',
  lapas: 'Perskaitytas lapas',
  klausimas: 'Atsakytas klausimas',
  grazinta: 'Prieš grąžinant',
  kita: 'Kita',
});

export function sourceLabel(saltinis) {
  return SOURCE_LABELS[saltinis] || SOURCE_LABELS.kita;
}

/** „2026-10-16T11:02:09Z" → „spalio 16 d. 14:02" in his time zone; '' for a bad stamp. */
export function versionTime(iso, { now = Date.now() } = {}) {
  const d = new Date(iso);
  if (!iso || Number.isNaN(d.getTime())) return '';
  const time = d.toLocaleTimeString('lt-LT', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Vilnius' });
  const day = (x) => x.toLocaleDateString('lt-LT', { timeZone: 'Europe/Vilnius' });
  const today = new Date(now);
  if (day(d) === day(today)) return `šiandien ${time}`;
  if (day(d) === day(new Date(now - 86400000))) return `vakar ${time}`;
  const date = d.toLocaleDateString('lt-LT', { month: 'long', day: 'numeric', timeZone: 'Europe/Vilnius' });
  return `${date} ${time}`;
}

/** „54 KB" — the stored size, so he can see history is not free but small. */
export function versionSize(bytes) {
  const n = Number(bytes);
  if (!Number.isFinite(n) || n <= 0) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / 1024 / 1024).toLocaleString('lt-LT', { maximumFractionDigits: 1 })} MB`;
}

/** One list row: what it is and when, newest first as the server sends it. */
export function versionRows(versions, opts) {
  return (Array.isArray(versions) ? versions : []).map((v) => ({
    id: v.id,
    when: versionTime(v.created_at, opts),
    source: v.saltinis,
    sourceText: sourceLabel(v.saltinis),
    title: v.pavadinimas || '',
    size: versionSize(v.suspausta),
    current: !!v.dabartine,
  }));
}

/**
 * The diff as sections for the drawer: [{title, lines}], only the non-empty ones. `diff` is the server's
 * answer (api/version_diff.py) — every item already carries its sentence.
 */
export function diffSections(diff) {
  const d = diff && typeof diff === 'object' ? diff : {};
  const texts = (items) => (Array.isArray(items) ? items : []).map((x) => x?.text).filter(Boolean);
  const rooms = d.patalpos || {};
  const rows = d.eilutes || {};
  return [
    { key: 'patalpos', title: 'Patalpos', lines: [...texts(rooms.pridetos), ...texts(rooms.pasalintos), ...texts(rooms.pakeistos)] },
    { key: 'eilutes', title: 'Sąmatos eilutės', lines: [...texts(rows.pridetos), ...texts(rows.istrintos), ...texts(rows.pakeistos)] },
    { key: 'prielaidos', title: 'Prielaidos', lines: texts(d.prielaidos?.pakeistos) },
  ].filter((s) => s.lines.length);
}

async function call(path, init) {
  const r = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(path.id)}/versions${path.rest || ''}`, {
    credentials: 'include', ...init,
  });
  if (!r.ok) {
    const err = new Error(`versions ${r.status}`);
    err.status = r.status;
    throw err;
  }
  return r.json();
}

export const fetchVersions = (projectId) => call({ id: projectId }).then((b) => b.versions || []);
export const fetchVersionDiff = (projectId, a, b = 'dabartine') =>
  call({ id: projectId, rest: `/${encodeURIComponent(a)}/diff/${encodeURIComponent(b)}` });
export const restoreVersion = (projectId, versionId) =>
  call({ id: projectId, rest: `/${encodeURIComponent(versionId)}/restore` }, { method: 'POST' });
