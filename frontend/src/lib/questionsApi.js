/**
 * questionsApi — the network half of Patikra's question list (see lib/questions.js).
 * One read for the whole project; the server saves nothing.
 */

import { API_BASE } from '@/lib/apiBase';

/** `{questions: [...], asked, read, rooms}` — backend/extractor/project_questions.py */
export async function fetchQuestions(projectId, { signal } = {}) {
  const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectId)}/questions`, {
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
