// legendReview — „Pažymėti legendą" (key G), the pure part (Pathon v3 W2-B; design 2026-10-18 §4 B, §5 Legend row).
//
// The flow: the program proposes the sheet's legend (W1-E `legenda` zone, read by POST …/legend/rows), he
// accepts it or draws his own box; the rows are counted (POST …/legend/count); he reviews them row by row
// (✔ keep / 🗑 drop / „Kitas pavadinimas") and mark by mark (✕ on the drawing); ONE „Sukurti kiekius (N)"
// creates the count types and their marks. Nothing exists before that click, and the click has Undo.
//
// After the click a count type made from a legend row carries `legend_row_id`; its sąmata row follows the
// count live (`syncLegendRows`) — no „Į sąmatą" click — with the sentence „suskaičiuota pagal legendą: …".
//
// Geometry: everything the legend routes answer is in DISPLAY-frame page fractions (top-left origin, /Rotate
// applied — the frame of the room outlines and evidence crops); count marks live in UNROTATED mediabox PDF
// points (lib/measurements). `displayPctToMediaPt` is the one crossing.

import { inverseRotatePctPoint } from './viewerEngine/pageRotation.js';
import { makeCountType, makeMeasurement } from './measurements.js';

export const LEGEND_SOURCE = 'legenda';
// found by the program and reviewed by him — drawn hollow like „Rasti panašius" marks (lib/overlayTokens)
export const LEGEND_CONFIDENCE = 'yellow';
// accepted marks sent to the training corpus per row (every removed one is sent): a busy legend must not
// queue hundreds of renders behind one click
export const MAX_ACCEPTS_PER_ROW = 20;
// …and at most this many in all, removed ones first: the route renders the sheet for each and allows 30 a minute
export const MAX_DECISIONS = 60;

/** The session's phases, in order. `null` = the tool is off. */
export const LEGEND_PHASES = ['suggesting', 'proposed', 'box', 'reading', 'counting', 'review', 'creating'];

// ── geometry ───────────────────────────────────────────────────────────────────────────────────────────

/** A display-frame fraction point → top-left mediabox points. `page = {size: {width, height}, rotation}`. */
export function displayPctToMediaPt(x, y, page) {
  const w = Number(page?.size?.width);
  const h = Number(page?.size?.height);
  if (!(w > 0 && h > 0)) return null;
  const [mx, my] = inverseRotatePctPoint(Number(x), Number(y), page?.rotation ?? 0);
  return { x: Math.round(mx * w * 100) / 100, y: Math.round(my * h * 100) / 100 };
}

/** A display-frame box [x0, y0, x1, y1] → the same box in top-left mediabox points. */
export function displayBoxToMediaBox(box, page) {
  if (!Array.isArray(box) || box.length !== 4) return null;
  const a = displayPctToMediaPt(box[0], box[1], page);
  const b = displayPctToMediaPt(box[2], box[3], page);
  if (!a || !b) return null;
  return [Math.min(a.x, b.x), Math.min(a.y, b.y), Math.max(a.x, b.x), Math.max(a.y, b.y)];
}

/** Two drag corners (fractions) → a box, or null when it is too small to hold a legend. */
export function boxFromPctDrag(a, b, minSide = 0.01) {
  if (!a || !b) return null;
  const box = [Math.min(a.x, b.x), Math.min(a.y, b.y), Math.max(a.x, b.x), Math.max(a.y, b.y)]
    .map((v) => Math.round(Math.min(1, Math.max(0, v)) * 10000) / 10000);
  if (box[2] - box[0] < minSide || box[3] - box[1] < minSide) return null;
  return box;
}

/**
 * The smallest frame he can draw round a legend, in SCREEN pixels per side. Screen, not PDF points: the frame is
 * aimed on the screen, and a point size would depend on the zoom and the sheet (A1 vs A4). 16 px is about the
 * smallest thing a pointer aims at on purpose; a click or a slip of the hand is below it, a real legend (the signs
 * with their names) is hundreds of pixels at any usable zoom. Below it the frame is NOT sent to the server.
 */
export const MIN_FRAME_PX = 16;

/** Two drag corners (fractions) on a width x height px page: is the frame too small to be a legend? (a click is) */
export function frameTooSmall(a, b, width, height, minPx = MIN_FRAME_PX) {
  if (!a || !b || !(width > 0) || !(height > 0)) return true;
  return Math.abs(b.x - a.x) * width < minPx || Math.abs(b.y - a.y) * height < minPx;
}

export function pointInBox(box, x, y) {
  return Array.isArray(box) && x >= box[0] && x <= box[2] && y >= box[1] && y <= box[3];
}

// ── the rows answer ────────────────────────────────────────────────────────────────────────────────────

/** POST …/legend/rows → the proposals to show on the sheet: [{id, page, bbox_pct, rows}], legends with rows only. */
export function proposalsFrom(answer) {
  const page = Number(answer?.page) || null;
  return (Array.isArray(answer?.legends) ? answer.legends : [])
    .filter((l) => Array.isArray(l?.bbox_pct) && l.bbox_pct.length === 4 && Array.isArray(l.rows) && l.rows.length)
    .map((l, i) => ({ id: `${page}:${i}`, page, bbox_pct: l.bbox_pct, rows: l.rows }));
}

/** The rows of the accepted legends, each once (two zones can hold the same row). */
export function rowsOf(legends) {
  const seen = new Set();
  const out = [];
  for (const l of legends || []) {
    for (const r of l?.rows || []) {
      if (!r?.row_id || seen.has(r.row_id)) continue;
      seen.add(r.row_id);
      out.push(r);
    }
  }
  return out;
}

// ── review ─────────────────────────────────────────────────────────────────────────────────────────────

/**
 * The review's starting point — every reading starts from a proposal: a countable row the counter found
 * marks for is proposed ✔; a row with nothing found, a material sample or a failed count is proposed 🗑
 * (he can still keep it and mark the pieces by hand). → {[row_id]: {keep, name}}
 */
export function initialReview(rows, counts = {}) {
  const out = {};
  for (const r of rows || []) {
    const c = counts[r.row_id];
    // marks to show, not the counter's number: a candidate standing on text-layer letters is listed, never a mark
    out[r.row_id] = { keep: !!(r.countable !== false && c && c.status === 'ok' && (c.instances || []).length > 0), name: null };
  }
  return out;
}

export const instanceId = (rowId, i) => `${rowId}#${i}`;

/** A row's instances he has not removed, with their ids. */
export function keptInstances(countRow, removed = new Set()) {
  return (countRow?.instances || [])
    .map((inst, i) => ({ ...inst, id: instanceId(countRow.row_id, i) }))
    .filter((inst) => !removed.has(inst.id));
}

/** {page: n} of a list of instances, pages in order: [{page, n}]. */
export function perPage(instances) {
  const by = new Map();
  for (const i of instances || []) by.set(i.page, (by.get(i.page) || 0) + 1);
  return [...by.entries()].sort((a, b) => a[0] - b[0]).map(([page, n]) => ({ page, n }));
}

/** „ženklas / ženklai / ženklų" — the Lithuanian count form. */
export function marksWord(n) {
  const k = Math.abs(Number(n) || 0);
  if (k % 10 === 1 && k % 100 !== 11) return 'ženklas';
  if (k % 10 >= 2 && k % 10 <= 9 && (k % 100 < 12 || k % 100 > 19)) return 'ženklai';
  return 'ženklų';
}

/** „3 ženklai lape 1, 1 ženklas lape 3" — or „ženklų nerasta". */
export function perPageText(list) {
  const parts = (list || []).filter((p) => p.n > 0).map((p) => `${p.n} ${marksWord(p.n)} lape ${p.page}`);
  return parts.length ? parts.join(', ') : 'ženklų nerasta';
}

/** The name a row's count type gets: his „Kitas pavadinimas", else the legend text. */
export function rowName(row, review) {
  const own = String(review?.name || '').trim();
  return own || String(row?.text || '').trim() || 'Ženklas';
}

/** The rows he kept („Tinka") that can be counted — with marks or without. */
export function keptRows(rows, review) {
  return (rows || []).filter((r) => r.countable !== false && review?.[r.row_id]?.keep);
}

/**
 * What „Sukurti kiekius (N)" counts: the kept rows with at least one kept mark. A count is never claimed
 * for a row the drawing shows no mark of (`blankRows`).
 */
export function rowsToCreate(rows, review, counts = {}, removed = new Set()) {
  return keptRows(rows, review).filter((r) => keptInstances(counts?.[r.row_id], removed).length > 0);
}

/** The kept rows with no mark left: each becomes a BLANK sąmata row with the question, never a count. */
export function blankRows(rows, review, counts = {}, removed = new Set()) {
  return keptRows(rows, review).filter((r) => keptInstances(counts?.[r.row_id], removed).length === 0);
}

/** Why a kept legend row stands blank in the sąmata — said beside the row before the click, and on the row. */
export const BLANK_REASON = 'legendoje yra, brėžinyje ženklų nerasta — suskaičiuokite „Kiekis“ įrankiu';

/** The blank sąmata row of a kept legend row with no marks: kiekis empty, the reason, no ledger count. */
export function blankSamataRow(row, review) {
  return {
    id: `${LEGEND_ROW_PREFIX}be-zenklu-${row.row_id}`,
    aprasymas: `${rowName(row, review)} (pagal legendą)`,
    mato_vnt: 'vnt.',
    kiekis: null,
    kaina: 0,
    skyrius: 'Matavimai',
    confidence: 'low',
    saltinis: 'legenda',
    legend_row_id: row.row_id,
    _confidence_reason: BLANK_REASON[0].toUpperCase() + BLANK_REASON.slice(1),
    ledger_note_lt: BLANK_REASON,
  };
}

/** The button's label. */
export function createLabel(n) {
  return `Sukurti kiekius (${n})`;
}

/**
 * „Sukurti kiekius": the count types and their marks. `pages[pageNr - 1] = {size, rotation}` (the viewer's
 * document pages). A row already made into a type earlier (same `legend_row_id`) keeps its type: the new marks
 * replace its old legend marks, hand-placed ones stay. → {types (new ones), marks, replaceTypeIds, made: [{row,
 * type, marks}]}
 */
export function buildCreate({ rows, counts, review, removed = new Set(), countTypes = [], pages = [] }) {
  const existing = [...countTypes];
  const types = [];
  const marks = [];
  const replaceTypeIds = [];
  const made = [];
  for (const row of rowsToCreate(rows, review, counts, removed)) {
    const name = rowName(row, review[row.row_id]);
    let type = countTypes.find((t) => t.legend_row_id === row.row_id) || null;
    if (type) {
      replaceTypeIds.push(type.id);
      if (type.label !== name || !type.eilute_id) type = { ...type, label: name, eilute_id: type.eilute_id || legendRowId(type.id), kaip: type.kaip || 'kiekis' };
    } else {
      const made = makeCountType(name, existing);
      // the link to its sąmata row rides on the type (lib/measuredRows honours a link on the object): the row's
      // kiekis IS the marks, on every save and through /recompute-interior's rebuild
      type = { ...made, legend_row_id: row.row_id, legend_text: String(row.text || ''), eilute_id: legendRowId(made.id), kaip: 'kiekis' };
      existing.push(type);
      types.push(type);
    }
    const rowMarks = [];
    for (const inst of keptInstances(counts?.[row.row_id], removed)) {
      const page = pages[inst.page - 1];
      const box = inst.box_pct;
      const c = Array.isArray(box) ? displayPctToMediaPt((box[0] + box[2]) / 2, (box[1] + box[3]) / 2, page) : null;
      if (!c) continue;
      rowMarks.push(makeMeasurement('count', inst.page, [c], {
        typeId: type.id,
        color: type.color,
        confidence: LEGEND_CONFIDENCE,
        source: LEGEND_SOURCE,
        legend_row_id: row.row_id,
        box: displayBoxToMediaBox(box, page),
        ...(inst.score != null ? { score: Math.round(Number(inst.score) * 1000) / 1000 } : {}),
      }));
    }
    marks.push(...rowMarks);
    made.push({ row, type, marks: rowMarks });
  }
  const blanks = blankRows(rows, review, counts, removed).map((r) => blankSamataRow(r, review[r.row_id]));
  return { types, marks, replaceTypeIds, made, blanks, renamed: made.map((m) => m.type).filter((t) => replaceTypeIds.includes(t.id)) };
}

/**
 * The measurements and types after a create: the replaced types' old LEGEND marks go, the new marks come.
 * Pure, so the Undo is the same function's inputs kept aside.
 */
export function applyCreate(measurements, countTypes, plan) {
  const replace = new Set(plan.replaceTypeIds || []);
  const renamed = new Map((plan.renamed || []).map((t) => [t.id, t]));
  const nextMeasurements = [
    ...(measurements || []).filter((m) => !(m.kind === 'count' && replace.has(m.typeId) && m.source === LEGEND_SOURCE)),
    ...(plan.marks || []),
  ];
  const nextTypes = [...(countTypes || []).map((t) => renamed.get(t.id) || t), ...(plan.types || [])];
  return { measurements: nextMeasurements, countTypes: nextTypes };
}

// ── what is sent to the corpus and the journal ─────────────────────────────────────────────────────────

/**
 * /api/cv/record-decision bodies (minus project_id): every removed mark is a reject, kept marks of a kept row
 * are accepts (at most MAX_ACCEPTS_PER_ROW per row). Marks of a dropped row are not judged one by one — the
 * row was. `klassOf(row)` names the class.
 */
export function decisionsFor({ rows, counts, review, removed = new Set(), pages = [], klassOf }) {
  const out = [];
  for (const row of rows || []) {
    const c = counts?.[row.row_id];
    if (!c) continue;
    const keep = !!review?.[row.row_id]?.keep;
    let accepts = 0;
    (c.instances || []).forEach((inst, i) => {
      const gone = removed.has(instanceId(row.row_id, i));
      if (!gone && (!keep || accepts >= MAX_ACCEPTS_PER_ROW)) return;
      const boxPt = displayBoxToMediaBox(inst.box_pct, pages[inst.page - 1]);
      if (!boxPt || boxPt[2] - boxPt[0] <= 0 || boxPt[3] - boxPt[1] <= 0) return;
      if (!gone) accepts += 1;
      out.push({
        page_idx: inst.page - 1, box_pt: boxPt, klass: klassOf(row), decision: gone ? 'reject' : 'accept',
        confidence: inst.score ?? null, source: LEGEND_SOURCE,
      });
    });
  }
  const rejects = out.filter((d) => d.decision === 'reject');
  const accepts = out.filter((d) => d.decision === 'accept');
  return [...rejects, ...accepts].slice(0, MAX_DECISIONS);
}

/** One corrections-journal row per reviewed legend row (source „legenda"); a material sample was never a choice. */
export function journalRows({ rows, counts, review, removed = new Set() }) {
  return (rows || []).filter((row) => row.countable !== false).map((row) => {
    const c = counts?.[row.row_id];
    const keep = row.countable !== false && !!review?.[row.row_id]?.keep;
    const kept = keptInstances(c, removed).length;
    return {
      field_path: `legenda.${row.page}.${row.row_id}`,
      old_value: { eilute: String(row.text || ''), rasta: c?.count ?? 0 },
      new_value: {
        sprendimas: keep ? 'accept' : 'reject',
        pavadinimas: keep ? rowName(row, review?.[row.row_id]) : null,
        kiekis: keep ? kept : 0,
        pasalinta: (c?.count ?? 0) - kept,
      },
      source: LEGEND_SOURCE,
      note: c?.saltinis || null,
    };
  });
}

/** The legend as api/legends.py stores it (ProjectLegend.rows): the kept rows with his names. */
export function legendRowsToSave(rows, review) {
  return keptRows(rows, review).map((r) => ({
    row_id: r.row_id, page: r.page, glyph_bbox_pct: r.glyph_bbox_pct, glyph_box_pt: r.glyph_box_pt ?? null,
    glyph_kind: r.glyph_kind ?? null, colour: r.colour ?? null, glyph_text: r.glyph_text ?? null,
    text: String(r.text || ''), text_bbox_pct: r.text_bbox_pct ?? null, legend_bbox_pct: r.legend_bbox_pct ?? null,
    countable: r.countable !== false, name: String(review?.[r.row_id]?.name || '').trim() || null,
  }));
}

// ── reuse (B4): an earlier project's legend ───────────────────────────────────────────────────────────

/** The text a row is matched by across projects: lower case, one space, no punctuation at the ends. */
export function rowKey(text) {
  return String(text || '').toLowerCase().replace(/\s+/g, ' ').replace(/^[\s\-–—•·:.]+|[\s\-–—•·:.]+$/g, '').trim();
}

/**
 * Does a saved legend (an earlier project's, or the architect's) fit the rows read here? → {matched, total,
 * review} where `review` carries his earlier names and keeps for the matching rows, or null when fewer than
 * half of the rows (and fewer than two) match — another architect's legend is not offered.
 */
export function matchSavedLegend(rows, saved, base = {}) {
  const savedRows = (Array.isArray(saved?.rows) ? saved.rows : []).filter((r) => rowKey(r?.text));
  if (!savedRows.length || !rows?.length) return null;
  const byKey = new Map(savedRows.map((r) => [rowKey(r.text), r]));
  const review = { ...base };
  let matched = 0;
  for (const r of rows) {
    const s = byKey.get(rowKey(r.text));
    if (!s) continue;
    matched += 1;
    review[r.row_id] = { keep: r.countable !== false, name: s.name ? String(s.name) : null };
  }
  if (matched < 2 || matched * 2 < rows.length) return null;
  return { matched, total: rows.length, review };
}

// ── the sąmata rows that follow the counts (B3) ───────────────────────────────────────────────────────

const LEGEND_ROW_PREFIX = 'rnk-legenda-';

/** The id of a legend count type's sąmata row (`rnk-` — a recompute carries it like a hand-added row). */
export function legendRowId(typeId) {
  return `${LEGEND_ROW_PREFIX}${typeId}`;
}

/** The sentence a legend row's ledger shows. `manual` = marks he placed by hand on top. */
export function legendLedgerText(text, pages, manual = 0) {
  const base = `suskaičiuota pagal legendą: eilutė „${String(text || '').trim()}“, ${perPageText(pages)}`;
  return manual > 0 ? `${base} (iš jų ${manual} pažymėta rankiniu būdu)` : base;
}

/**
 * The ledger line of a legend count type's row — lib/measuredRows uses it as the type's `tekstas`, so the row
 * says „suskaičiuota pagal legendą: eilutė „…“, 3 ženklai lape 1" instead of a plain „matavimas".
 */
export function legendTypeText(type, measurements) {
  const marks = (measurements || []).filter((m) => m?.kind === 'count' && m.typeId === type?.id);
  return legendLedgerText(type?.legend_text || type?.label, perPage(marks), marks.filter((m) => m.source !== LEGEND_SOURCE).length);
}

/**
 * The sąmata rows of the legend count types (B3): a type made from a legend row gets ONE row — id
 * `rnk-legenda-<type>` (the type's `eilute_id`), `quantity_source: 'measurement_count'`, unit vnt. — created here
 * the first time the type is saved; from then on its `kiekis` follows the marks through lib/measuredRows (the
 * type carries `kaip: 'kiekis'`), on every save and through /recompute-interior. A legend row whose type is gone
 * (Atšaukti) is removed. Returns the SAME array when nothing changed (callers skip the save).
 */
export function syncLegendRows(rows, measurements, countTypes) {
  const list = Array.isArray(rows) ? rows : [];
  const legendTypes = (countTypes || []).filter((t) => t?.legend_row_id);
  const typeIds = new Set(legendTypes.map((t) => t.id));
  let changed = false;
  const out = [];
  for (const r of list) {
    const ours = r?.legend_row_id && r.quantity_source === 'measurement_count';
    if (ours && !typeIds.has(r.measure_type_id)) { changed = true; continue; }
    out.push(r);
  }
  for (const t of legendTypes) {
    const id = t.eilute_id || legendRowId(t.id);
    if (out.some((r) => String(r?.id) === String(id) || (r?.measure_type_id === t.id && r.quantity_source === 'measurement_count'))) continue;
    const marks = (measurements || []).filter((m) => m.kind === 'count' && m.typeId === t.id);
    out.push({
      id,
      eil_nr: out.reduce((m, d) => Math.max(m, Number(d?.eil_nr) || 0), 0) + 1,
      aprasymas: `${t.label} (pagal legendą)`,
      mato_vnt: 'vnt.',
      kiekis: marks.length,
      kaina: 0,
      skyrius: 'Matavimai',
      confidence: 'medium',
      saltinis: 'legenda',
      quantity_source: 'measurement_count',
      measure_type_id: t.id,
      legend_row_id: t.legend_row_id,
    });
    changed = true;
  }
  return changed ? out : list;
}

// ── what every outcome says (B1-B, 2026-10-19) ────────────────────────────────────────────────────────
// The founder's first walk: „it does not get calculated when I mark something". Every way the tool ends —
// counted, nothing in the box, a legend with no marks on the plan, only material samples, an error, out of
// time — now ends in ONE plain sentence in the pill and the panel, and the failures offer „Bandyti dar kartą".

/** Lithuanian count forms: [one, few (2–9), many (0, 10–20)] by the number's last digits. */
function form(n, [one, few, many]) {
  const k = Math.abs(Number(n) || 0);
  if (k % 10 === 1 && k % 100 !== 11) return one;
  if (k % 10 >= 2 && k % 10 <= 9 && (k % 100 < 12 || k % 100 > 19)) return few;
  return many;
}
export const rowsWord = (n) => form(n, ['eilutė', 'eilutės', 'eilučių']);
/** „1 lape", „3 lapuose" — where. */
export const onSheetsText = (n) => `${n} ${form(n, ['lape', 'lapuose', 'lapuose'])}`;

/** {rows: countable rows, marks, pages} of a count answer (every mark found, before he removes any). */
export function countSummary(rows, counts = {}) {
  const countable = (rows || []).filter((r) => r.countable !== false);
  const pages = new Set();
  let marks = 0;
  for (const r of countable) {
    for (const inst of counts?.[r.row_id]?.instances || []) {
      marks += 1;
      pages.add(inst.page);
    }
  }
  return { rows: countable.length, samples: (rows || []).length - countable.length, marks, pages: pages.size };
}

/** „Rasta 14 eilučių, 38 ženklai 3 lapuose" */
export function summaryText({ rows, marks, pages }) {
  return `Rasta ${rows} ${rowsWord(rows)}, ${marks} ${marksWord(marks)} ${onSheetsText(pages)}`;
}

/**
 * The review's outcome sentence. state = {rows, counts, countError} → {tone: ok | empty | warn | error, text,
 * retry} — `retry` = „Bandyti dar kartą" counts the same rows again.
 */
export function reviewOutcome({ rows = [], counts = {}, countError = null } = {}) {
  const s = countSummary(rows, counts);
  if (countError) {
    return { tone: 'error', retry: true, short: 'Ženklų suskaičiuoti nepavyko',
      text: `Ženklų suskaičiuoti nepavyko: ${countError}. Legendos eilutes matote — bandykite dar kartą arba žymėkite ženklus „Kiekis“ įrankiu.` };
  }
  if (!s.rows) {
    return { tone: 'empty', retry: false, short: 'Tik medžiagų pavyzdžiai — matuokite plotu ar ilgiu',
      text: 'Šioje legendoje tik medžiagų ar linijų pavyzdžiai — jie matuojami plotu ar ilgiu, ne vienetais. Prie eilutės spauskite „Matuoti plotą“ arba „Matuoti ilgį“.' };
  }
  const partial = (rows || []).some((r) => counts?.[r.row_id]?.partial);
  if (!s.marks) {
    return { tone: partial ? 'warn' : 'empty', retry: partial, short: 'Legenda perskaityta, ženklų plane nerasta',
      text: `Legendą perskaičiau (${s.rows} ${rowsWord(s.rows)}), bet ženklų plane neradau${partial ? ' — ne visi lapai spėti peržiūrėti' : ''}. Pažymėkite juos „Kiekis“ įrankiu; eilutė su „Tinka“ sąmatoje liks tuščia, su klausimu.` };
  }
  if (partial) {
    return { tone: 'warn', retry: true, short: `${summaryText(s)} · ne visi lapai`,
      text: `${summaryText(s)}. Ne visi lapai spėti peržiūrėti per minutę — bandykite dar kartą.` };
  }
  return { tone: 'ok', retry: false, short: summaryText(s), text: `${summaryText(s)}.` };
}

/**
 * A plain Lithuanian sentence for a failed request — never the browser's own words („Load failed" in Safari,
 * „Failed to fetch" in Chrome, „signal timed out"), which used to reach the screen as they were.
 */
export function requestErrorText(e) {
  const name = e?.name || '';
  if (name === 'TimeoutError') return 'serveris neatsakė per skirtą laiką';
  if (name === 'AbortError') return 'užklausa nutraukta';
  if (e?.status === 429) return 'per daug užklausų iš eilės — palaukite minutę';
  if (e?.status >= 500) return 'serverio klaida';
  const msg = String(e?.message || '').trim();
  if (name === 'TypeError' || /load failed|failed to fetch|networkerror|network error/i.test(msg)) {
    return 'nepavyko pasiekti serverio — patikrinkite ryšį';
  }
  // the server's own Lithuanian detail is kept; anything else is not shown to him as it is
  return e?.status && msg && !/^HTTP \d+$/.test(msg) ? msg : 'nežinoma klaida';
}

/** The legend this box holds no rows of — the plain sentence, with why when the reader said why. */
export const BOX_EMPTY = 'Šiame rėmelyje legendos nėra — pažymėkite legendą su ženklais ir tekstu';
export function boxFailureText(answer) {
  if (answer?.status === 'be_teksto') {
    return 'Šiame lape nėra teksto (jis nuskenuotas kaip paveikslėlis) — legendos perskaityti negaliu. Ženklus pažymėkite „Kiekis“ įrankiu.';
  }
  const why = String(answer?.detail || '');
  if (/nėra teksto eilučių/.test(why)) return `${BOX_EMPTY}. Rėmelyje nėra jokio teksto.`;
  if (/be ženklo/.test(why)) return `${BOX_EMPTY}. Rėmelyje tik tekstas be ženklų šalia — pvz. patalpų lentelė, pastabos ar antspaudas.`;
  return `${BOX_EMPTY}.`;
}

/** No legend on the sheet on screen: where it is, when another sheet carries one. */
export function noLegendText(page, elsewhere = []) {
  const others = (elsewhere || []).map((p) => p.page).filter((p) => p !== page);
  if (!others.length) return 'Šiame lape legendos neradau — apveskite ją rėmeliu';
  const list = others.length === 1 ? `${others[0]} lape` : `${others.slice(0, 3).join(', ')} lapuose`;
  return `Šiame lape legendos nėra. Legenda yra ${list} — eikite ten arba apveskite ją rėmeliu čia`;
}

/** The sheet „Eiti į N lapą" opens: the first other sheet with a legend, while he has none on screen. */
export function legendGotoPage({ phase, page, failure, outcome, elsewhere } = {}) {
  if (phase !== 'box' || failure || outcome) return null;
  return (elsewhere || []).map((p) => p.page).find((p) => p !== page) || null;
}

// ── the words at the cursor and in the pill ───────────────────────────────────────────────────────────

/** The sentence beside the pointer for the legend tool's phase. */
export function legendCursorHint(phase) {
  switch (phase) {
    case 'suggesting': return 'Ieškau legendos šiame lape…';
    case 'proposed': return 'Spustelėkite pasiūlytą legendą — tinka · arba tempkite rėmelį per kitą';
    case 'box': return 'Tempdami apveskite legendą — ženklus ir jų pavadinimus';
    case 'reading': return 'Skaitau rėmelį…';
    case 'counting': return 'Skaičiuoju ženklus — gali užtrukti iki minutės';
    case 'review': return 'Spustelėkite neteisingą žymę — pašalinti · dešinėje — eilutės';
    case 'creating': return 'Kuriami kiekiai…';
    default: return null;
  }
}

/** „Skaičiuoju… 12 s — gali užtrukti iki minutės" */
export function countingText(elapsedS = 0) {
  const s = Math.max(0, Math.floor(Number(elapsedS) || 0));
  return `Skaičiuoju… ${s} s — gali užtrukti iki minutės`;
}

/**
 * The bottom pill for the legend tool. state = {phase, proposals (n), toCreate (n), blanks (n), notice, elapsed (s),
 * outcome ({text, retry}), gotoPage} → {id, name, detail, keys, actions}
 */
export function legendPill({ phase, proposals = 0, toCreate = 0, blanks = 0, notice = null, elapsed = 0, outcome = null, gotoPage = null, frameHint = null } = {}) {
  const name = 'Pažymėti legendą';
  const exit = { id: 'legendExit', label: 'Išeiti', title: 'Išeiti iš legendos įrankio (Esc) — niekas nesukuriama' };
  const retry = { id: 'legendRetry', label: 'Bandyti dar kartą', primary: true, title: 'Paleisti dar kartą' };
  if (phase === 'proposed') {
    return {
      id: 'legend', name, detail: frameHint || (proposals > 1 ? `Tai legendos? (${proposals})` : 'Tai legenda?'),
      keys: 'Enter — taip · Esc — išeiti',
      actions: [
        { id: 'legendAccept', label: 'Taip', primary: true, title: 'Taip, tai legenda — skaityti jos eilutes ir skaičiuoti ženklus (Enter)' },
        { id: 'legendRedraw', label: 'Nubrėžti kitaip', title: 'Apvesti legendą rėmeliu patiems' },
      ],
    };
  }
  if (phase === 'suggesting' || phase === 'reading' || phase === 'counting') {
    const detail = phase === 'suggesting' ? 'Ieškau legendos šiame lape…'
      : phase === 'reading' ? 'Skaitau rėmelį…'
        : countingText(elapsed);
    return { id: 'legend', name, detail, keys: 'Esc — nutraukti', actions: [exit] };
  }
  if (phase === 'box') {
    const actions = [];
    // drawing by hand: the proposal he turned down stays on the drawing, its "Taip" stays reachable
    if (proposals > 0) actions.push({ id: 'legendAccept', label: 'Taip', primary: true, title: 'Taip, pasiūlytas rėmelis yra legenda — skaityti jos eilutes ir skaičiuoti ženklus (Enter)' });
    if (outcome?.retry) actions.push(retry);
    if (gotoPage) actions.push({ id: 'legendGoto', label: `Į ${gotoPage} lapą`, primary: !outcome?.retry && !proposals, title: `Eiti į ${gotoPage} lapą — ten yra legenda` });
    return { id: 'legend', name, detail: frameHint || outcome?.short || outcome?.text || notice || null, keys: proposals > 0 ? 'Enter — taip · Esc — išeiti' : null, actions: [...actions, exit] };
  }
  if (phase === 'review' || phase === 'creating') {
    return {
      id: 'legend', name, detail: phase === 'creating' ? 'Kuriama…' : (outcome?.short || outcome?.text || 'Peržiūrėkite eilutes dešinėje'),
      keys: toCreate || blanks ? 'Enter — sukurti' : null,
      actions: [
        ...(outcome?.retry && phase === 'review' ? [{ ...retry, primary: false, title: 'Skaičiuoti ženklus dar kartą' }] : []),
        { id: 'legendCreate', label: createLabel(toCreate), primary: true, disabled: !(toCreate || blanks) || phase === 'creating', title: toCreate || blanks ? 'Sukurti pažymėtų eilučių kiekius ir žymes brėžinyje (Enter) — eilutės be ženklų sąmatoje liks tuščios; po to galėsite atšaukti' : 'Pažymėkite bent vieną eilutę „Tinka“' },
        { id: 'legendRedraw', label: 'Kita legenda', title: 'Apvesti kitą legendą — ši peržiūra išmetama' },
        exit,
      ],
    };
  }
  return { id: 'legend', name, detail: null, keys: null, actions: [exit] };
}
