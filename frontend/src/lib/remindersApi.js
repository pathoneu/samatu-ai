/**
 * remindersApi — the network half of the project's reminders (see lib/reminders.js).
 * One read for the whole project; the server saves nothing.
 */
import { API_BASE } from '@/lib/apiBase';

/** `{reminders: [...], count}` — read-only, the server saves nothing. */
export async function fetchReminders(projectId, { signal } = {}) {
  const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectId)}/reminders`, {
    credentials: 'include',
    signal: signal || AbortSignal.timeout(60_000),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return body;
}
