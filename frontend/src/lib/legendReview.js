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
    out[r.row_id] = { keep: !!(r.countable !== false && c && c.status === 'ok' && c.count > 0), name: null };
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

/** What „Sukurti kiekius (N)" will create: the rows he kept that can be counted. */
export function rowsToCreate(rows, review) {
  return (rows || []).filter((r) => r.countable !== false && review?.[r.row_id]?.keep);
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
  for (const row of rowsToCreate(rows, review)) {
    const name = rowName(row, review[row.row_id]);
    let type = countTypes.find((t) => t.legend_row_id === row.row_id) || null;
    if (type) {
      replaceTypeIds.push(type.id);
      if (type.label !== name) type = { ...type, label: name };
    } else {
      type = { ...makeCountType(name, existing), legend_row_id: row.row_id, legend_text: String(row.text || '') };
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
  return { types, marks, replaceTypeIds, made, renamed: made.map((m) => m.type).filter((t) => replaceTypeIds.includes(t.id)) };
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

/** One corrections-journal row per reviewed legend row (source „legenda"). */
export function journalRows({ rows, counts, review, removed = new Set() }) {
  return (rows || []).map((row) => {
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
  return rowsToCreate(rows, review).map((r) => ({
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

/** The sentence a legend row's ledger shows. `manual` = marks he placed by hand on top. */
export function legendLedgerText(text, pages, manual = 0) {
  const base = `suskaičiuota pagal legendą: eilutė „${String(text || '').trim()}“, ${perPageText(pages)}`;
  return manual > 0 ? `${base} (iš jų ${manual} pažymėta rankiniu būdu)` : base;
}

/**
 * The sąmata rows of the legend count types, brought in line with the marks: a type made from a legend row
 * has ONE row (`quantity_source: 'measurement_count'`, id `rnk-legenda-…` so a recompute carries it like a
 * hand-added row), its `kiekis` = the marks of that type, its `ledger_note_lt` the sentence above. A row
 * whose quantity he typed himself keeps his number (only the sentence follows). A row whose type is gone is
 * removed. Returns the SAME array when nothing changed (callers skip the save).
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
    const marks = (measurements || []).filter((m) => m.kind === 'count' && m.typeId === t.id);
    const pages = perPage(marks);
    const manual = marks.filter((m) => m.source !== LEGEND_SOURCE).length;
    const note = legendLedgerText(t.legend_text || t.label, pages, manual);
    const idx = out.findIndex((r) => r?.measure_type_id === t.id && r.quantity_source === 'measurement_count');
    if (idx >= 0) {
      const cur = out[idx];
      const own = cur.manual_override === true;
      const next = {
        ...cur,
        ...(own ? {} : { kiekis: marks.length }),
        ledger_note_lt: note,
        legend_row_id: t.legend_row_id,
        aprasymas: cur.aprasymas,
      };
      if (next.kiekis !== cur.kiekis || next.ledger_note_lt !== cur.ledger_note_lt || next.legend_row_id !== cur.legend_row_id) {
        out[idx] = next;
        changed = true;
      }
    } else {
      out.push({
        id: `${LEGEND_ROW_PREFIX}${t.id}`,
        eil_nr: out.length + 1,
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
        ledger_note_lt: note,
      });
      changed = true;
    }
  }
  return changed ? out : list;
}

// ── the words at the cursor and in the pill ───────────────────────────────────────────────────────────

/** The sentence beside the pointer for the legend tool's phase. */
export function legendCursorHint(phase) {
  switch (phase) {
    case 'suggesting': return 'Ieškoma legendos šiame lape…';
    case 'proposed': return 'Spustelėkite pasiūlytą legendą — tinka · arba tempkite rėmelį per kitą';
    case 'box': return 'Tempdami apveskite legendą — ženklus ir jų pavadinimus';
    case 'reading': return 'Skaitomos legendos eilutės…';
    case 'counting': return 'Skaičiuojami ženklai brėžinyje…';
    case 'review': return 'Spustelėkite neteisingą žymę — pašalinti · dešinėje — eilutės';
    case 'creating': return 'Kuriami kiekiai…';
    default: return null;
  }
}

/**
 * The bottom pill for the legend tool. state = {phase, proposals (n), toCreate (n), notice} →
 * {id, name, detail, keys, actions}
 */
export function legendPill({ phase, proposals = 0, toCreate = 0, notice = null } = {}) {
  const name = 'Pažymėti legendą';
  const exit = { id: 'legendExit', label: 'Išeiti', title: 'Išeiti iš legendos įrankio (Esc) — niekas nesukuriama' };
  if (phase === 'proposed') {
    return {
      id: 'legend', name, detail: proposals > 1 ? `Tai legendos? (${proposals})` : 'Tai legenda?',
      keys: 'Enter — taip · Esc — išeiti',
      actions: [
        { id: 'legendAccept', label: 'Taip', primary: true, title: 'Taip, tai legenda — skaityti jos eilutes ir skaičiuoti ženklus (Enter)' },
        { id: 'legendRedraw', label: 'Nubrėžti kitaip', title: 'Apvesti legendą rėmeliu patiems' },
      ],
    };
  }
  if (phase === 'box' || phase === 'suggesting' || phase === 'reading' || phase === 'counting') {
    const detail = phase === 'suggesting' ? 'Ieškoma legendos…'
      : phase === 'reading' ? 'Skaitomos eilutės…'
        : phase === 'counting' ? 'Skaičiuojami ženklai — gali užtrukti iki minutės'
          : (notice || null);
    return { id: 'legend', name, detail, keys: null, actions: [exit] };
  }
  if (phase === 'review' || phase === 'creating') {
    return {
      id: 'legend', name, detail: phase === 'creating' ? 'Kuriama…' : 'Peržiūrėkite eilutes dešinėje',
      keys: toCreate ? 'Enter — sukurti' : null,
      actions: [
        { id: 'legendCreate', label: createLabel(toCreate), primary: true, disabled: !toCreate || phase === 'creating', title: toCreate ? 'Sukurti pažymėtų eilučių kiekius ir žymes brėžinyje (Enter) — po to galėsite atšaukti' : 'Pažymėkite bent vieną eilutę ✔' },
        { id: 'legendRedraw', label: 'Kita legenda', title: 'Apvesti kitą legendą — ši peržiūra išmetama' },
        exit,
      ],
    };
  }
  return { id: 'legend', name, detail: null, keys: null, actions: [exit] };
}
