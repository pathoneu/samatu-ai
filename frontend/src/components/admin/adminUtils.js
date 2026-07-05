/**
 * Shared helpers for the Admin v2 cockpit — formatting + a thin admin fetch
 * wrapper. Kept framework-free so every panel component can import cheaply.
 *
 * All money is EUR, all figures render tabular-nums in the UI (callers apply
 * the class). Number formatting is lt-LT throughout.
 */
import { API_BASE as API } from '@/lib/apiBase';

/** GET an admin endpoint with cookie auth. Throws on non-2xx with the status. */
export async function fetchAdmin(path) {
  const res = await fetch(`${API}${path}`, { credentials: 'include' });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body — keep the status string */
    }
    throw new Error(detail);
  }
  return res.json();
}

/** POST an admin action (disable/enable). Same error semantics as fetchAdmin. */
export async function postAdmin(path) {
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* keep status */
    }
    throw new Error(detail);
  }
  return res.json();
}

/** Trigger a credentialed CSV download via a hidden anchor (keeps the cookie). */
export function downloadCsv(path, filename) {
  const url = `${API}${path}`;
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || '';
  // Same-origin in prod (app.pathon.eu ↔ api.pathon.eu share cookies via
  // credentials); the browser sends cookies on a top-level navigation-style
  // download when the anchor targets the same site.
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

const _eur = new Intl.NumberFormat('lt-LT', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const _eur4 = new Intl.NumberFormat('lt-LT', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});
const _int = new Intl.NumberFormat('lt-LT', { maximumFractionDigits: 0 });

/** €12,345.67 — 2 decimals, lt-LT grouping. */
export function fmtEur(n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return '—';
  return `${_eur.format(v)} €`;
}

/** For small per-call figures where 2dp rounds to 0 (avg €/extraction). */
export function fmtEurPrecise(n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return '—';
  return `${_eur4.format(v)} €`;
}

/** 12,345 — integer with grouping. */
export function fmtInt(n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return '—';
  return _int.format(v);
}

/** Human byte sizes: 1.4 MB, 812 KB, … */
export function fmtBytes(bytes) {
  const b = Number(bytes);
  if (!Number.isFinite(b) || b <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let v = b;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  const dp = v < 10 && i > 0 ? 1 : 0;
  return `${v.toFixed(dp)} ${units[i]}`;
}

/** ISO / SQL timestamp → 2026-07-05 lt-LT date. '—' on empty. */
export function fmtDate(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return String(ts);
  return d.toLocaleDateString('lt-LT');
}

/** ISO / SQL timestamp → date + time. */
export function fmtDateTime(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return String(ts);
  return d.toLocaleString('lt-LT', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Short axis label MM-DD from a YYYY-MM-DD date string. */
export function fmtAxisDate(ts) {
  if (!ts) return '';
  // series dates are 'YYYY-MM-DD' — slice avoids a TZ shift from Date parsing.
  const s = String(ts);
  return s.length >= 10 ? s.slice(5) : s;
}

/** "prieš 3 val." style relative time for recent-activity timestamps. */
export function fmtRelative(ts) {
  if (!ts) return 'niekada';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return String(ts);
  const diffMs = Date.now() - d.getTime();
  const sec = Math.round(diffMs / 1000);
  if (sec < 60) return 'ką tik';
  const min = Math.round(sec / 60);
  if (min < 60) return `prieš ${min} min.`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `prieš ${hr} val.`;
  const day = Math.round(hr / 24);
  if (day < 30) return `prieš ${day} d.`;
  return fmtDate(ts);
}

/**
 * Fill calendar gaps in a daily series so charts show a continuous x-axis.
 * The backend omits zero-activity days; we densify to `days` buckets ending
 * today (UTC). Missing days get zeroed metrics.
 */
export function densifySeries(series, days) {
  const byDate = new Map((series || []).map((r) => [r.date, r]));
  const out = [];
  const today = new Date();
  for (let i = days - 1; i >= 0; i -= 1) {
    const d = new Date(today);
    d.setUTCDate(d.getUTCDate() - i);
    const key = d.toISOString().slice(0, 10);
    out.push(
      byDate.get(key) || {
        date: key,
        signups: 0,
        projects: 0,
        extractions: 0,
        cost_eur: 0,
        revenue_eur: 0,
      },
    );
  }
  return out;
}
