/**
 * legendApi — the network half of „Pažymėti legendą" (Pathon v3 W2-B; lib/legendReview.js is the pure half).
 *
 *   POST /api/projects/{id}/legend/rows    the sheet's suggested legends, or the rows of a box he drew (€0)
 *   POST /api/projects/{id}/legend/count   how many of each row's symbol the drawing carries (€0)
 *   GET/POST /api/legends/{id}             the project's legend — written only when he creates the counts
 *   GET /api/projects/{id}/legend/architect, POST …/legend/architect/promote — reuse on the next project
 *   POST /api/cv/record-decision           each mark he kept or removed → the training corpus
 *   POST /api/projects/{id}/corrections    one journal row per legend row (source „legenda")
 *
 * The two reading routes save nothing; nothing here calls a model.
 */
import { API_BASE } from './apiBase.js';
import { recordDecision } from './cvToolsApi.js';

const DECISION_GAP_MS = 2_100;
const wait = (ms) => new Promise((r) => { setTimeout(r, ms); });

async function call(path, { method = 'GET', body = null, timeoutMs = 90_000 } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: 'include',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(timeoutMs),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

const pid = (projectId) => encodeURIComponent(projectId);

/** The sheet's suggested legends (`bboxPct` absent) or the rows inside his box. */
export function fetchLegendRows(projectId, { page, bboxPct = null }) {
  return call(`/api/projects/${pid(projectId)}/legend/rows`, {
    method: 'POST', body: { page: Number(page), ...(bboxPct ? { bbox_pct: bboxPct } : {}) }, timeoutMs: 60_000,
  });
}

/** Counts for the rows (the route's own budget is 60 s; a little more here for the network). */
export function countLegendRows(projectId, rows) {
  return call(`/api/projects/${pid(projectId)}/legend/count`, { method: 'POST', body: { rows }, timeoutMs: 120_000 });
}

export function loadProjectLegend(projectId) {
  return call(`/api/legends/${pid(projectId)}`);
}

/** The whole project legend (api/legends.py ProjectLegend). */
export function saveProjectLegend(projectId, { rows = [], symbols = [], architect = null } = {}) {
  return call(`/api/legends/${pid(projectId)}`, {
    method: 'POST', body: { project_id: projectId, architect: architect || null, symbols, rows },
  });
}

/** The caller's legend for an architect, through this project (owner check first). */
export function loadArchitectLegend(projectId, architect) {
  const q = architect ? `?architect=${encodeURIComponent(architect)}` : '';
  return call(`/api/projects/${pid(projectId)}/legend/architect${q}`);
}

/** Promote this project's legend (+ his earlier ones of the same architect) — opt-in, ≥ 2 projects. */
export function promoteArchitectLegend(projectId, architect, verifiedInProjects) {
  return call(`/api/projects/${pid(projectId)}/legend/architect/promote`, {
    method: 'POST', body: { architect, opt_in: true, verified_in_projects: verifiedInProjects },
  });
}

export function logLegendCorrection(projectId, row) {
  return call(`/api/projects/${pid(projectId)}/corrections`, { method: 'POST', body: row });
}

/**
 * Send the decisions and journal rows one after another, never in his way. Resolves to the number that
 * failed (the caller says so once).
 */
export async function sendLegendLearning(projectId, { decisions = [], journal = [] } = {}) {
  let failed = 0;
  for (const row of journal) {
    try { await logLegendCorrection(projectId, row); } catch { failed += 1; }
  }
  // the route allows 30 a minute per person: one every ~2 s, and one retry after a minute's pause on a 429
  for (let i = 0; i < decisions.length; i += 1) {
    if (i) await wait(DECISION_GAP_MS);
    try {
      await recordDecision({ project_id: projectId, ...decisions[i] });
    } catch (e) {
      if (/429|Too Many/i.test(String(e?.message || ''))) {
        await wait(60_000);
        try { await recordDecision({ project_id: projectId, ...decisions[i] }); } catch { failed += 1; }
      } else failed += 1;
    }
  }
  return failed;
}

// ── the architects he named (reuse, B4) ───────────────────────────────────────────────────────────────
// The project blob has no architect field: he names the projektuotojas once in the review panel, and the
// browser remembers which of his projects carried which name, so the next project can be offered the earlier
// legend. Per browser — the legends themselves live on the server.
const ARCHITECTS_KEY = 'samatu_legend_architects';

export function readArchitects(storage = (typeof window !== 'undefined' ? window.localStorage : null)) {
  try {
    const raw = JSON.parse(storage?.getItem(ARCHITECTS_KEY) || '{}');
    return raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {};
  } catch { return {}; }
}

/** Remember that `projectId` carries `architect` → the names and their projects, newest last. */
export function rememberArchitect(architect, projectId, storage = (typeof window !== 'undefined' ? window.localStorage : null)) {
  const name = String(architect || '').trim();
  if (!name || !projectId) return readArchitects(storage);
  const all = readArchitects(storage);
  const list = (Array.isArray(all[name]) ? all[name] : []).filter((p) => p !== projectId);
  all[name] = [...list, projectId].slice(-20);
  try { storage?.setItem(ARCHITECTS_KEY, JSON.stringify(all)); } catch { /* private mode */ }
  return all;
}
