// viewSettings — how the drawing is shown, per browser (Pathon v3 W5-B, B4; coverage #141, #142, #111, #140, #11).
//
//   drawing   „Brėžinio ryškumas" (opacity 0,2–1), „Išvalyti foną" (lightens the near-white grey of a scan to
//             white: 0 = off … 0,4), „Nespalvotai" (greyscale) — only the drawing; the marks keep their colours;
//   labels    room names and the measurements' values on the drawing, on or off (the same switch is the
//             „Užrašai" choice of „PDF su žymėjimais");
//   zones     „Rodyti sritis" — the sheet's plan, legends, tables, title block and notes outlined (B2);
//   crosshair a full-canvas crosshair at the pointer;
//   pro       the pro layer's switch — OFF by default; behind it the room outlines' fill and line width (#140,
//             the founder decides whether it stays).
//
// Nothing here changes a number: view only. Pure — the popover is components/viewer/ViewSettingsPopover.jsx and
// the CSS is applied by TakeoffViewer through viewCss().

export const VIEW_SETTINGS_KEY = 'samatu_viewer_view';

export const VIEW_DEFAULTS = Object.freeze({
  opacity: 1,
  cleanBg: 0,
  gray: false,
  names: true,
  dims: true,
  zones: false,
  crosshair: false,
  pro: false,
  polyOpacity: 0.16,
  lineWidth: 2,
});

const clamp = (v, lo, hi, dflt) => {
  const n = Number(v);
  return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : dflt;
};

/** A settings object with every field in range (unknown keys dropped, bad values → the default). */
export function sanitizeViewSettings(raw) {
  const r = raw && typeof raw === 'object' ? raw : {};
  const bool = (k) => (typeof r[k] === 'boolean' ? r[k] : VIEW_DEFAULTS[k]);
  return {
    opacity: clamp(r.opacity, 0.2, 1, VIEW_DEFAULTS.opacity),
    cleanBg: clamp(r.cleanBg, 0, 0.4, VIEW_DEFAULTS.cleanBg),
    gray: bool('gray'),
    names: bool('names'),
    dims: bool('dims'),
    zones: bool('zones'),
    crosshair: bool('crosshair'),
    pro: bool('pro'),
    polyOpacity: clamp(r.polyOpacity, 0, 0.6, VIEW_DEFAULTS.polyOpacity),
    lineWidth: clamp(r.lineWidth, 1, 6, VIEW_DEFAULTS.lineWidth),
  };
}

export function readViewSettings(storage = (typeof window !== 'undefined' ? window.localStorage : null)) {
  try {
    return sanitizeViewSettings(JSON.parse(storage?.getItem?.(VIEW_SETTINGS_KEY) || '{}'));
  } catch {
    return { ...VIEW_DEFAULTS };
  }
}

export function writeViewSettings(settings, storage = (typeof window !== 'undefined' ? window.localStorage : null)) {
  try { storage?.setItem?.(VIEW_SETTINGS_KEY, JSON.stringify(sanitizeViewSettings(settings))); } catch { /* private mode */ }
}

/** True when anything differs from the defaults (the popover's button shows it is on). */
export function viewChanged(settings) {
  const s = sanitizeViewSettings(settings);
  return Object.keys(VIEW_DEFAULTS).some((k) => k !== 'pro' && s[k] !== VIEW_DEFAULTS[k] && !(!s.pro && (k === 'polyOpacity' || k === 'lineWidth')));
}

/** The SVG filter's slope for „Išvalyti foną": every grey lighter than 1 − t becomes white. */
export function cleanSlope(t) {
  const v = clamp(t, 0, 0.4, 0);
  return Math.round((1 / (1 - v)) * 1000) / 1000;
}

export const CLEAN_FILTER_ID = 'tv-clean-bg';

/**
 * The style rules for the settings, scoped to one viewer root ([data-tv-root]): the drawing's opacity and
 * filter (on the page's render wrapper `[data-drawing-render]`, never the marks), hidden labels, and the pro
 * layer's outline fill and width. '' when everything is at its default.
 */
export function viewCss(settings) {
  const s = sanitizeViewSettings(settings);
  const rules = [];
  const filters = [];
  if (s.cleanBg > 0) filters.push(`url(#${CLEAN_FILTER_ID})`);
  if (s.gray) filters.push('grayscale(1)');
  const drawing = [];
  if (s.opacity < 1) drawing.push(`opacity: ${s.opacity}`);
  if (filters.length) drawing.push(`filter: ${filters.join(' ')}`);
  if (drawing.length) rules.push(`[data-tv-root] [data-drawing-render] { ${drawing.join('; ')}; }`);
  if (!s.names) rules.push('[data-tv-root] [data-room-label], [data-tv-root] [data-ov-label="name"] { display: none; }');
  if (!s.dims) rules.push('[data-tv-root] [data-ov-label="dim"] { display: none; }');
  if (s.pro) {
    rules.push(`[data-tv-root] g[data-room-zone] > polygon, [data-tv-root] g[data-room-zone] > rect { fill-opacity: ${s.polyOpacity}; stroke-width: ${s.lineWidth}px; }`);
  }
  return rules.join('\n');
}
