/**
 * samataTemplateApi.js — the two network calls the template layout makes.
 *
 *   • GET  /api/samata-templates                 — does this account have one?
 *   • POST /api/projects/{id}/samata-render      — the project in his layout
 *
 * Both are owner-scoped on the backend (`api/samata_templates.py`); the render
 * writes nothing, so calling it on every change of `darbu_sarasas` is safe and
 * cheap. The Excel export in his layout goes through ExportDropdown's existing
 * download path with `?layout=template` — see there.
 */

import { API_BASE } from './apiBase.js';

async function readError(res) {
  const body = await res.json().catch(() => ({}));
  const err = new Error(body.detail || `HTTP ${res.status}`);
  err.status = res.status;
  return err;
}

// One list per page load, shared by the Sąmata step, the export menu and the
// room sheet. `refresh` bypasses it after a template is created or deleted.
let templatesPromise = null;

/** The caller's templates (`[{id, name, is_default, n_projects, …}]`). */
export function fetchSamataTemplates({ refresh = false, signal } = {}) {
  if (!templatesPromise || refresh) {
    templatesPromise = fetch(`${API_BASE}/api/samata-templates`, {
      credentials: 'include', signal,
    }).then(async (res) => {
      if (!res.ok) throw await readError(res);
      const body = await res.json();
      return Array.isArray(body?.samata_templates) ? body.samata_templates : [];
    }).catch((err) => {
      templatesPromise = null;   // do not cache a failure
      throw err;
    });
  }
  return templatesPromise;
}

/** Test seam. */
export function _resetTemplatesCache() {
  templatesPromise = null;
}

/**
 * The project rendered through a template.
 *
 * Pass `rows` (the darbu_sarasas the screen is holding) and `rooms` to render
 * exactly what the contractor sees — the store is write-through and lags a
 * keystroke behind, so rendering the saved blob showed his typed number one
 * edit late. Without `rows` the backend renders the saved project.
 *
 * Resolves `{eilutes, santrauka, sablonas}`; 404 when the account has no
 * template (the UI hides the layout switch in that case, so this is rare).
 */
export async function renderSamata(projectId, {
  templateId, includeOptional = true, rows = null, rooms = null, signal,
} = {}) {
  const params = new URLSearchParams();
  if (templateId) params.set('template_id', templateId);
  if (!includeOptional) params.set('include_optional', '0');
  const qs = params.toString();
  const url = `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/samata-render${qs ? `?${qs}` : ''}`;
  const init = { method: 'POST', credentials: 'include', signal };
  if (Array.isArray(rows)) {
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify({ darbu_sarasas: rows, patalpos: Array.isArray(rooms) ? rooms : [] });
  }
  const res = await fetch(url, init);
  if (!res.ok) throw await readError(res);
  return res.json();
}

/** The rooms the render phrases its blank note from — same list the sheet reads. */
export function roomsForRender(project) {
  return project?.v8_rooms?.length ? project.v8_rooms : (project?.patalpos || []);
}
