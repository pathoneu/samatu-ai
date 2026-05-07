/**
 * Centralized API base URL. Production frontend lives on app.pathon.eu;
 * backend on api.pathon.eu. Vercel deployments inject VITE_API_BASE at
 * build time; local dev (vite proxy) leaves it empty so /api/... resolves
 * via vite.config.js dev proxy.
 */
export const API_BASE = import.meta.env?.VITE_API_BASE || '';
