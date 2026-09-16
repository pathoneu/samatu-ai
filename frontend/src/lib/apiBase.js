/**
 * Centralized API base URL. Production frontend lives on app.pathon.eu;
 * backend on api.pathon.eu. Vercel deployments inject VITE_API_BASE at
 * build time; local dev (vite proxy) leaves it empty so /api/... resolves
 * via vite.config.js dev proxy.
 */
// VITE_API_SAME_ORIGIN=1 (2026-09-16): a Vercel preview of the `dev` branch
// talks to its own origin and vercel.json rewrites proxy the backend paths to
// the Railway dev service — first-party cookies, no DNS, no CORS. Production
// (app.pathon.eu) keeps VITE_API_BASE.
export const API_BASE = import.meta.env?.VITE_API_SAME_ORIGIN === '1'
  ? ''
  : (import.meta.env?.VITE_API_BASE || '');
