/**
 * errorTracker — lightweight error capture for free public testing phase
 * (Sprint §24, 2026-04-29).
 *
 * Goals:
 *  - Catch window errors + unhandled promise rejections
 *  - Keep last 100 entries in localStorage so user can export them
 *  - No external service (Sentry comes later w/ auth re-enable)
 *  - Doesn't disturb existing console.error usage
 *
 * Structure of each entry:
 *  {
 *    ts: ISO string,
 *    type: 'error' | 'unhandled' | 'manual',
 *    message: string,
 *    stack: string | null,
 *    url: string,            // page path
 *    project_id: string|null // if /project/<id> URL
 *  }
 */

const KEY = 'samatu_error_log';
const MAX_ENTRIES = 100;

// Browser noise that is NOT an application error. "ResizeObserver loop
// completed with undelivered notifications" is fired by the spec whenever a
// resize callback dirties layout again in the same frame — every virtualised
// list / auto-sizing panel does this. Chrome surfaces it on window.onerror
// with no stack and no user-visible effect. During the 2026-07-27 production
// run it was the ONLY thing in /api/log-error, which masked the real errors
// we were hunting for. Filter at the source, not in the log reader.
const BENIGN_ERROR_PATTERNS = [
  /^ResizeObserver loop/i,
];

export function isBenignError(message) {
  const msg = String(message || '');
  return BENIGN_ERROR_PATTERNS.some((re) => re.test(msg));
}

function safeRead() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function safeWrite(entries) {
  try {
    localStorage.setItem(KEY, JSON.stringify(entries.slice(-MAX_ENTRIES)));
  } catch {
    // localStorage full — drop oldest 50
    try { localStorage.setItem(KEY, JSON.stringify(entries.slice(-50))); } catch {}
  }
}

function projectIdFromUrl() {
  const m = (typeof window !== 'undefined' ? window.location.pathname : '').match(/\/project\/([0-9a-f-]+)/i);
  return m ? m[1] : null;
}

export function logError(type, message, stack = null, extra = {}) {
  if (typeof window === 'undefined') return;
  if (isBenignError(message)) return;
  const entry = {
    ts: new Date().toISOString(),
    type,
    message: String(message || '').slice(0, 1000),
    stack: stack ? String(stack).slice(0, 4000) : null,
    url: window.location.pathname + window.location.search,
    project_id: projectIdFromUrl(),
    ...extra,
  };
  const entries = safeRead();
  entries.push(entry);
  safeWrite(entries);
}

export function getErrorLog() {
  return safeRead();
}

export function clearErrorLog() {
  try { localStorage.removeItem(KEY); } catch {}
}

export function exportErrorLog() {
  const entries = safeRead();
  const payload = {
    version: 1,
    exported_at: new Date().toISOString(),
    user_agent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
    entries_count: entries.length,
    entries,
  };
  return JSON.stringify(payload, null, 2);
}

export function downloadErrorLog() {
  if (typeof window === 'undefined') return;
  const json = exportErrorLog();
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const today = new Date().toISOString().slice(0, 10);
  const a = document.createElement('a');
  a.href = url;
  a.download = `samatu-klaidos-${today}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

let initialized = false;
// Sprint §AUDIT (2026-04-29): use a module-level marker on console.error so
// HMR re-imports don't stack wrappers. If our wrapper is already installed
// (detected by sentinel property), skip wrapping again.
const WRAP_SENTINEL = '__samatuErrorWrapped';

export function initErrorTracker() {
  if (initialized || typeof window === 'undefined') return;
  initialized = true;

  window.addEventListener('error', (e) => {
    logError('error', e.message, e.error?.stack, {
      filename: e.filename,
      lineno: e.lineno,
      colno: e.colno,
    });
  });

  window.addEventListener('unhandledrejection', (e) => {
    const msg = e.reason?.message || String(e.reason || 'Unhandled rejection');
    logError('unhandled', msg, e.reason?.stack);
  });

  // Wrap console.error so frontend log captures intentional .error() calls
  // (but doesn't disturb output — original behavior preserved).
  // Sprint §AUDIT: HMR-safe — sentinel prevents stacking wrappers across
  // hot reloads in dev mode.
  if (!console.error[WRAP_SENTINEL]) {
    const original = console.error;
    const wrapped = (...args) => {
      try {
        const msg = args.map(a => {
          if (a instanceof Error) return a.message;
          if (typeof a === 'object') {
            try { return JSON.stringify(a); } catch { return String(a); }
          }
          return String(a);
        }).join(' ');
        logError('manual', msg, args.find(a => a instanceof Error)?.stack);
      } catch { /* never crash here */ }
      original.apply(console, args);
    };
    wrapped[WRAP_SENTINEL] = true;
    console.error = wrapped;
  }
}
