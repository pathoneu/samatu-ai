/**
 * scaleLineApi — the network half of the „Skaičius" tool (see lib/scaleLine.js). The server reads the string under
 * the line and, when it finds one, stores the sheet's scale (append-only; the newest in force); a line over nothing
 * comes back as a normal answer with `status: 'blank'` and a reason, not as an error.
 */
import { API_BASE } from './apiBase.js';

/** `{status: 'ok', page, scale}` | `{status: 'blank', page, reason}`; throws with `.status` / `.userMessage` on HTTP errors. */
export async function postScaleLine(projectId, body, { signal } = {}) {
  const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectId)}/geometry/scale-line`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: signal || AbortSignal.timeout(60_000),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${res.status}`);
    err.status = res.status;
    err.userMessage = typeof data.detail === 'string' ? data.detail : null;
    throw err;
  }
  return data;
}
