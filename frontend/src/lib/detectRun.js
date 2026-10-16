/**
 * detectRun — the pure progress model of „Perskaityti lapą" (api/detect_run.py).
 *
 * The server reads the drawing (€0, no Vision) in named stages and answers
 * with a snapshot: `{stage, stages: [{id, label_lt, about_lt, status, note}],
 * result_ready, failed, result?}`. The LAST stage, „kiekiai", is the
 * browser's: the read is merged into the project and the rows are rebuilt
 * through /recompute-interior (lib/freeRereadApi.landFreeRereadResult). This
 * module folds the browser's part into the server's snapshot, says what the
 * pill shows, which features a choice needs, and what the toast reports.
 * Pure; no React, no I/O.
 */

import { ltCount } from './ltPlural.js';

export const STAGE_IDS = Object.freeze(['mastelis', 'tekstas', 'planas', 'konturai', 'angos', 'sienos', 'grindys', 'kiekiai']);
export const FEATURES = Object.freeze(['plotai', 'konturai', 'sienos', 'angos', 'grindys']);

/**
 * What each feature needs read first (mirrors api/detect_run.REQUIRES). An outline and its openings come together:
 * the lane writes the openings in the frame of the room's own outline.
 */
export const REQUIRES = Object.freeze({
  plotai: [], konturai: ['plotai', 'angos'], sienos: ['konturai'], angos: ['konturai'], grindys: ['plotai'],
});

export const FEATURE_LABELS = Object.freeze({
  plotai: 'Patalpos ir plotai',
  konturai: 'Kontūrai',
  sienos: 'Sienų ilgiai (perimetrai)',
  angos: 'Angos (durys, langai)',
  grindys: 'Grindų danga',
});

export const FEATURE_HINTS = Object.freeze({
  plotai: 'Visada skaitoma — be jų nežinoma, kur stovi patalpos.',
  konturai: 'Patalpų kontūrai iš brėžinio sienų, kartu su jų angomis. Jūsų pataisyti kontūrai nekeičiami.',
  sienos: 'Sienų ilgiai sudedami iš plano matmenų. Reikia kontūrų.',
  angos: 'Durys ir langai kontūro sienose — skaitomi kartu su kontūrais.',
  grindys: 'Danga, nubraižyta grindų plane.',
});

// Shown before the server's first answer, and when a snapshot lacks its stage list.
const FALLBACK_LABELS = Object.freeze({
  mastelis: 'Mastelis', tekstas: 'Tekstas', planas: 'Planas', konturai: 'Kontūrai',
  angos: 'Angos', sienos: 'Sienos', grindys: 'Grindys', kiekiai: 'Kiekiai',
});

export const allFeatures = () => Object.fromEntries(FEATURES.map((f) => [f, true]));

/**
 * Tick or untick one feature and keep the choice consistent: ticking one ticks what it needs, unticking one
 * unticks what needs it. „plotai" is always on.
 */
export function toggleFeature(selected, feature, on) {
  const next = { ...allFalse(), ...(selected || {}) };
  if (!FEATURES.includes(feature) || feature === 'plotai') return { ...next, plotai: true };
  const set = (f, v) => {
    if (next[f] === v) return;
    next[f] = v;
    if (v) REQUIRES[f].forEach((need) => set(need, true));
    else FEATURES.filter((g) => REQUIRES[g].includes(f)).forEach((g) => set(g, false));
  };
  set(feature, Boolean(on));
  next.plotai = true;
  return next;
}

function allFalse() {
  return Object.fromEntries(FEATURES.map((f) => [f, false]));
}

/** At least one feature beyond „plotai"? (the picker's start buttons are disabled otherwise) */
export function canStart(selected) {
  return FEATURES.some((f) => f !== 'plotai' && selected?.[f]);
}

/** The POST body. `pages` = [n] for one sheet, 'all' for the set. */
export function requestBody(pages, selected) {
  const features = Object.fromEntries(FEATURES.map((f) => [f, Boolean(selected?.[f]) || f === 'plotai']));
  return { pages: pages === 'all' ? 'all' : [...new Set(pages.map(Number))].filter((n) => n >= 1).sort((a, b) => a - b), features };
}

/**
 * The view of one run: the server's snapshot with the browser's „kiekiai" folded in.
 * `client` = null | {status: 'running'|'done'|'failed', note}.
 * Returns {stages, current, done, failed, failedStage, progress, terminal}.
 */
export function viewOf(snapshot, client = null) {
  const src = Array.isArray(snapshot?.stages) && snapshot.stages.length
    ? snapshot.stages
    : STAGE_IDS.map((id) => ({ id, label_lt: FALLBACK_LABELS[id], about_lt: '', status: 'pending', note: null }));
  const stages = src.map((s) => {
    const out = { id: s.id, label: s.label_lt || FALLBACK_LABELS[s.id] || s.id, about: s.about_lt || '', status: s.status || 'pending', note: s.note || null };
    // the server hands „kiekiai" over (`perduota`): until the browser lands the read it is still running
    if (out.status === 'perduota') out.status = 'running';
    if (s.id === 'kiekiai' && client && snapshot?.result_ready) {
      out.status = client.status;
      out.note = client.note ?? out.note;
    }
    return out;
  });
  const failedStage = stages.find((s) => s.status === 'failed') || null;
  const finished = (s) => s.status === 'done' || s.status === 'skipped' || s.status === 'failed';
  const done = !failedStage && stages.every((s) => s.status === 'done' || s.status === 'skipped');
  const current = stages.find((s) => s.status === 'running') || failedStage
    || (done ? stages[stages.length - 1] : stages.find((s) => s.status === 'pending')) || null;
  const progress = stages.length ? stages.filter(finished).length / stages.length : 0;
  return { stages, current, done, failed: Boolean(failedStage), failedStage, progress, terminal: done || Boolean(failedStage) };
}

/** Should the browser keep asking the server? */
export function needsPolling(snapshot) {
  return Boolean(snapshot?.job) && !snapshot?.result_ready && !snapshot?.failed;
}

/** One glyph per status — the stage list's left column. */
export function statusMark(status) {
  return { done: '✓', running: '●', skipped: '–', failed: '✕' }[status] || '○';
}

/** The pill's headline. */
export function headline(view, pages) {
  const where = pages === 'all' ? 'visi lapai' : `pritaikoma lapui ${Array.isArray(pages) ? pages.join(', ') : pages}`;
  if (!view) return '';
  if (view.failed) return `Nepavyko: ${view.failedStage.label} (${where})`;
  if (view.done) return `Perskaityta (${where})`;
  const i = view.current ? view.stages.findIndex((s) => s.id === view.current.id) + 1 : 0;
  return `${view.current?.label || 'Pradedama'}… ${i}/${view.stages.length} (${where})`;
}

const WALL_OUTLINES = new Set(['vektoriniai_konturai', 'sienu_konturas', 'corrected', 'manual']);
const HIS_OUTLINES = new Set(['corrected', 'manual']);
const FROM_DIMENSIONS = new Set(['matmenu_eilutes', 'plano_matmenys']);

/**
 * What the read's rooms now have — counted on the MERGED project (what he has after the merge kept his verified
 * rooms), only over the rooms the run covered. A door between two outlined rooms is listed from both sides and
 * counted once (api/detect_run.openings_count).
 */
export function scopeCounts(project, scopeNrs) {
  const stored = Array.isArray(project?.v8_rooms) && project.v8_rooms.length ? project.v8_rooms : project?.patalpos;
  const want = new Set((scopeNrs || []).map(String));
  const rooms = (Array.isArray(stored) ? stored : []).filter((r) => r && typeof r === 'object' && want.has(String(r.nr ?? '').trim()));
  const src = (r, k) => String(r?.[k] || '');
  const outlined = new Set(rooms.filter((r) => r._angos_sienose && typeof r._angos_sienose === 'object').map((r) => String(r.nr).trim()));
  let angos = 0;
  for (const r of rooms) {
    const list = Array.isArray(r._angos_sienose?.angos) ? r._angos_sienose.angos : [];
    for (const a of list) {
      const beyond = String(a?.i ?? '');
      if (outlined.has(beyond) && beyond < String(r.nr).trim()) continue;
      angos += 1;
    }
  }
  return {
    patalpos: rooms.length,
    konturai: rooms.filter((r) => WALL_OUTLINES.has(src(r, 'polygon_source'))).length,
    jusu: rooms.filter((r) => HIS_OUTLINES.has(src(r, 'polygon_source'))).length,
    angos,
    perimetrai: rooms.filter((r) => FROM_DIMENSIONS.has(src(r, 'perimetras_saltinis'))).length,
    grindys: rooms.filter((r) => src(r, 'grindu_danga_saltinis') === 'grindu_planas').length,
  };
}

/** The toast: „8 kontūrai, 23 angos, 6 perimetrai iš matmenų" — only the parts the chosen features read. */
export function summaryText(counts, features = allFeatures()) {
  if (!counts?.patalpos) return 'Šiame lape eksplikacijos patalpų nerasta — niekas nepakeista.';
  const on = (f) => Boolean(features?.[f]);
  const parts = [
    on('konturai') && ltCount(counts.konturai, 'kontūras', 'kontūrai', 'kontūrų'),
    on('angos') && ltCount(counts.angos, 'anga', 'angos', 'angų'),
    on('sienos') && `${ltCount(counts.perimetrai, 'perimetras', 'perimetrai', 'perimetrų')} iš matmenų`,
    on('grindys') && `danga ${counts.grindys} iš ${counts.patalpos}`,
  ].filter(Boolean);
  const his = on('konturai') && counts.jusu ? ` Jūsų pataisyti kontūrai (${counts.jusu}) palikti.` : '';
  return `${parts.join(', ')}.${his}`;
}

/** The re-run's label: once the sheet's plan has been read, the button reads „iš naujo" (Togal's Re-Togal). */
export function buttonLabel(project, page) {
  const geo = project?._meta?.geometrija;
  const groups = Array.isArray(geo?.grupes) ? geo.grupes : [];
  const read = groups.some((g) => Array.isArray(g) && g.map(Number).includes(Number(page)));
  return read ? 'Perskaityti iš naujo' : 'Perskaityti lapą';
}
