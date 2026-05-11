/**
 * Frontend wrappers for the /api/cv/* routes.
 *
 * Mirror the FastAPI bodies in backend/api/cv_tools.py — keep field
 * names in sync. Production DPI defaults to 200 (matches the backend
 * Pydantic default); tests can override.
 */
import { API_BASE } from './apiBase';

const post = async (path, body) => {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `${path} failed: ${res.status}`);
  }
  return res.json();
};

export const matchTemplate = (body) => post('/api/cv/match-template', body);
export const magicWand = (body) => post('/api/cv/magic-wand', body);
export const recordDecision = (body) => post('/api/cv/record-decision', body);
