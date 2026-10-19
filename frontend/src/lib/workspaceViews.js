/**
 * workspaceViews — the ONE workspace and its four views (Pathon v3, design §3, wave-1 track A).
 *
 * The step rail (1 Brėžinys · 2 Patikra · 3 Sąmata · 4 Siųsti) stays the visible journey, but the steps
 * are views of the same workspace: the drawing canvas is mounted once and kept, the right panel is a
 * mode host. This module is the pure part of that frame — which panel a view opens, how much of the
 * width the drawing gets, and how a view maps to and from the URL — so the frame components stay thin
 * and the rules are tested without a browser.
 *
 * URLs stay what they were (every link, bookmark and test keeps working):
 *   /project/:id                       → brezinys
 *   /project/:id?step=samata|siusti    → samata | siusti   (?step=brezinys and an unknown step → brezinys)
 *   /project/:id?step=patikra          → patikra            (legacy spelling, still honoured)
 *   /project/:id/patikra               → patikra, the question list
 *   /project/:id/patikra?kambarys=04   → patikra, the room sheet of room 04
 *   /project/:id/patikra?etapas=bendri → patikra, the project-wide stage
 */

export const VIEWS = ['brezinys', 'patikra', 'samata', 'siusti'];

// The right panel's tabs, in strip order. Labels are the UI text (Lithuanian); ids are stable.
export const PANEL_TABS = [
  { id: 'patalpos', label: 'Patalpos ir eilutės' },
  { id: 'kiekiai', label: 'Kiekiai' },
  { id: 'patikra', label: 'Patikra' },
  { id: 'samata', label: 'Sąmata' },
  { id: 'pokalbis', label: 'Pokalbis' },
];

// Tabs that ARE a view: choosing one of them is choosing that step. The other three belong to the
// drawing view — the step rail and the tab strip can never disagree about where he is.
const VIEW_TABS = new Set(['patikra', 'samata']);
const BREZINYS_TABS = new Set(['patalpos', 'kiekiai', 'pokalbis']);

// What each step's panel shows as tabs (B1-D, after the founder's first walk: nine destinations on one
// screen — four steps and five tabs — and „a person could easily get lost"). The step needs only these; the
// other tabs wait under one „Daugiau ▾". The step rail stays the one way to move between steps.
export const STEP_TABS = {
  brezinys: ['patalpos', 'kiekiai'],
  patikra: ['patikra'],
  samata: ['samata'],
  siusti: [],
};

/**
 * `{ primary, more }` — the tabs a view's panel shows in its strip and the ones under „Daugiau ▾", both as
 * PANEL_TABS entries in strip order. The tab on screen is always in the strip (a „Pokalbis" opened from a
 * Kiekiai row's menu shows as the chosen tab, never hidden in the menu).
 */
export function panelTabsFor(view, activeTab = null) {
  const own = new Set(STEP_TABS[view] || []);
  if (activeTab) own.add(activeTab);
  return {
    primary: PANEL_TABS.filter((tab) => own.has(tab.id)),
    more: PANEL_TABS.filter((tab) => !own.has(tab.id)),
  };
}

/** Which panel a view opens with: 'patalpos' | 'patikra' | 'samata' | null (Siųsti has no panel). */
export function panelForView(view) {
  switch (view) {
    case 'brezinys': return 'patalpos';
    case 'patikra': return 'patikra';
    case 'samata': return 'samata';
    default: return null;
  }
}

/**
 * How much of the width the drawing gets in a view:
 *  'full'  — the drawing takes everything but the right panel (Brėžinys);
 *  'split' — the drawing and a wide panel side by side (Patikra; Sąmata in its compact form);
 *  'strip' — the drawing collapses to a 56 px strip and the content takes the width (Sąmata after
 *            „Išskleisti", Siųsti). The viewer stays mounted behind the strip.
 * `expanded` is the Sąmata „Išskleisti" switch; `noDrawing` (no PDF in storage) leaves nothing to show
 * beside the rows, so Sąmata takes the width by itself.
 */
// On the Sąmata step the sąmata IS the page (B1-D): the rows open across the width, the drawing waits as
// the strip, „Rodyti brėžinį" brings it back beside the rows.
export const SAMATA_EXPANDED_DEFAULT = true;

export function canvasModeForView(view, { expanded = false, noDrawing = false } = {}) {
  switch (view) {
    case 'brezinys': return 'full';
    case 'patikra': return 'split';
    case 'samata': return expanded || noDrawing ? 'strip' : 'split';
    default: return 'strip';
  }
}

/**
 * A click on a panel tab → where to go. `{ view, tab }`: a view tab switches the step; a drawing tab
 * opens on the drawing view (switching to it when he is elsewhere).
 */
export function selectTab(currentView, tab) {
  if (VIEW_TABS.has(tab)) return { view: tab, tab };
  if (BREZINYS_TABS.has(tab)) return { view: 'brezinys', tab };
  return { view: currentView, tab: panelForView(currentView) };
}

/** The tab a view shows: its own panel, except the drawing view keeps the drawing tab he last chose. */
export function tabForView(view, lastDrawingTab = 'patalpos') {
  if (view === 'brezinys') return BREZINYS_TABS.has(lastDrawingTab) ? lastDrawingTab : 'patalpos';
  return panelForView(view);
}

// ── URL ↔ view ─────────────────────────────────────────────────────────────────────────────────────

const PATIKRA_PATH = /^\/project\/[^/]+\/patikra\/?$/;
const OWN_PARAMS = ['step', 'kambarys', 'etapas'];

function toParams(search) {
  if (search instanceof URLSearchParams) return new URLSearchParams(search);
  return new URLSearchParams(typeof search === 'string' ? search : '');
}

/** `{ view, kambarys, etapas }` from a location's pathname and search. */
export function viewFromLocation(pathname = '', search = '') {
  const params = toParams(search);
  if (PATIKRA_PATH.test(pathname || '')) {
    return { view: 'patikra', kambarys: params.get('kambarys'), etapas: params.get('etapas') };
  }
  const step = params.get('step');
  const view = step && VIEWS.includes(step) ? step : 'brezinys';
  return { view, kambarys: null, etapas: null };
}

/** Which part of Patikra the panel shows: the question list, a room's sheet, or the project-wide stage. */
export function patikraSubview({ kambarys = null, etapas = null } = {}) {
  if (etapas) return 'general';
  if (kambarys) return 'room';
  return 'questions';
}

/**
 * The URL for a view. `keep` is the current search: parameters that are not the frame's own (e.g.
 * `?viewer=legacy`) survive a step change — losing them would remount the viewer on another engine.
 */
export function locationForView(projectId, view, { kambarys = null, etapas = null, keep = '' } = {}) {
  const id = encodeURIComponent(String(projectId ?? ''));
  const params = toParams(keep);
  OWN_PARAMS.forEach((k) => params.delete(k));
  let path = `/project/${id}`;
  if (view === 'patikra') {
    path += '/patikra';
    if (etapas) params.set('etapas', String(etapas));
    else if (kambarys != null && kambarys !== '') params.set('kambarys', String(kambarys));
  } else if (view === 'samata' || view === 'siusti') {
    params.set('step', view);
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

// ── Two-way highlight (A6) ─────────────────────────────────────────────────────────────────────────

/**
 * The viewer's `focus` for „show me this place" (`onRevealEvidence({page, rect_pct})`): `{page, rect,
 * nonce}` with the rect in display-frame page fractions, the whole sheet when none (or a malformed one) is
 * given; null when there is no page to go to. The nonce makes the same place asked for twice two jumps.
 */
export function revealTarget({ page = null, rect_pct = null } = {}, nonce = 0) {
  const p = Number(page);
  if (!Number.isInteger(p) || p < 1) return null;
  const ok = Array.isArray(rect_pct) && rect_pct.length === 4 && rect_pct.every((v) => Number.isFinite(Number(v)));
  return { page: p, rect: ok ? rect_pct.map(Number) : [0, 0, 1, 1], nonce };
}

// ── Right panel width ──────────────────────────────────────────────────────────────────────────────

// 'full': the panel beside the drawing (Brėžinys) — 340 px by default, 300–480, remembered per browser.
// 'split': the wide panel of Patikra / compact Sąmata — 58 % of the workspace by default, 480–960.
export const PANEL_LIMITS = {
  full: { min: 300, max: 480, initial: 340, key: 'samatu_panel_width' },
  split: { min: 480, max: 960, ratio: 0.58, key: 'samatu_panel_split_width' },
};

// The drawing never gets less than this beside a split panel — under it the sheet is unreadable.
export const MIN_SPLIT_CANVAS = 360;
export const STRIP_WIDTH = 56;

export function clampPanelWidth(width, mode = 'full') {
  const lim = PANEL_LIMITS[mode] || PANEL_LIMITS.full;
  const n = Number(width);
  if (!Number.isFinite(n)) return mode === 'split' ? null : lim.initial;
  return Math.round(Math.min(lim.max, Math.max(lim.min, n)));
}

export { browserStorage } from './browserStorage.js';

/** The stored width for a panel mode, clamped; null when nothing (valid) is stored. */
export function readPanelWidth(storage, mode = 'full') {
  const lim = PANEL_LIMITS[mode] || PANEL_LIMITS.full;
  try {
    const raw = storage?.getItem?.(lim.key);
    if (raw == null || raw === '') return null;
    const n = Number(raw);
    return Number.isFinite(n) ? clampPanelWidth(n, mode) : null;
  } catch {
    return null;
  }
}

export function writePanelWidth(storage, mode, width) {
  const lim = PANEL_LIMITS[mode] || PANEL_LIMITS.full;
  const w = clampPanelWidth(width, mode);
  if (w == null) return null;
  try { storage?.setItem?.(lim.key, String(w)); } catch { /* private mode: the width just is not kept */ }
  return w;
}

/**
 * The right panel's width in px for a canvas mode, or null when the panel takes the remaining width
 * ('strip'). `stored` is what he dragged it to (null = never). A split panel always leaves the drawing
 * at least MIN_SPLIT_CANVAS.
 */
export function panelWidthFor(mode, { workspaceWidth = 0, stored = null } = {}) {
  if (mode === 'strip') return null;
  if (mode === 'split') {
    const lim = PANEL_LIMITS.split;
    const want = stored ?? Math.round((workspaceWidth || 0) * lim.ratio);
    const roomForIt = workspaceWidth > 0 ? workspaceWidth - MIN_SPLIT_CANVAS : lim.max;
    return Math.max(Math.min(lim.min, roomForIt), Math.min(clampPanelWidth(want, 'split'), roomForIt));
  }
  return stored ?? PANEL_LIMITS.full.initial;
}
