// feedback — 👍 / 👎 plus one optional line (Pathon v3 W5-C, C10 / coverage #170, #203).
//
// Two things are rated: the paid read as a whole (offered once, after it), and a found symbol (👎 =
// „neieškoti tokių": the next „Rasti panašius" search leaves out what looks like it — api/feedback.py). Both
// are rows of the corrections journal (source `ivertinimas`); „Atšaukti" is one more row. No paid call.

import { API_BASE } from './apiBase.js';

const LINE_MAX = 200;

/** The body for POST …/feedback. `line` is trimmed and cut; an empty line is left out. */
export function feedbackBody({ kind, up = false, line = '', page = null, boxPct = null, klass = null, undo = false } = {}) {
  const body = { kind, up: Boolean(up) };
  const text = String(line || '').trim().slice(0, LINE_MAX);
  if (text) body.line = text;
  if (undo) body.undo = true;
  if (kind === 'simbolis') {
    body.page = page;
    body.box_pct = boxPct;
    if (klass) body.klass = String(klass).slice(0, 80);
  }
  return body;
}

/** A found mark's box (display-frame fractions, as the legend counter gives it) is a valid negative. */
export function validBoxPct(b) {
  return Array.isArray(b) && b.length === 4 && b.every((v) => Number.isFinite(Number(v)))
    && b[0] >= 0 && b[1] >= 0 && b[2] <= 1 && b[3] <= 1 && b[2] > b[0] && b[3] > b[1];
}

/** The read is offered for rating once per project, in this browser (a per-viewer convenience). */
export const readRatedKey = (projectId) => `samatu_read_rated:${projectId}`;

export function readRatingDue(project, storage) {
  if (!project?.id || !project?._meta?.model) return false;     // only a project the paid read made
  try {
    return storage?.getItem?.(readRatedKey(project.id)) !== '1';
  } catch {
    return true;
  }
}

export function markReadRated(projectId, storage) {
  try { storage?.setItem?.(readRatedKey(projectId), '1'); } catch { /* private window: asked again next time */ }
}

export async function sendFeedback(projectId, body) {
  const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectId)}/feedback`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}
