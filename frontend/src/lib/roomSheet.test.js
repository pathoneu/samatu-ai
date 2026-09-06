import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  FACT_ORDER, canOverrideWholeRow, cornersFromPolygon, estimateMinutes,
  factNeedsInput, factTone, findRowForQuantity, hasCornerTerms, isRoomVerified,
  isWholeSheet, orderFacts, prefillValue, progressSummary, rippleText,
  legacyKeyIsUnique, legacyRowKey, roomIndex, roomTitle, roomsInDrawingOrder,
  summarizeRipple, termRows, CROP_MIN_H_PCT, CROP_MIN_W_PCT, paddedCropRect,
  pageToCropPct, polygonToCropPct, adjustOpeningCount, countOpenings,
  firstPageOfType, setSymbolCount, stampVerified, symbolPageTypes,
  symbolRows,
  authorFigureRows, bboxToRectPct,
} from './roomSheet.js';

const SAMPLE = JSON.parse(
  readFileSync(new URL('./__fixtures__/roomFacts.sample.json', import.meta.url), 'utf8'),
);

// A `t` that records what the component would have asked i18n for.
const stubT = (key, vars) => JSON.stringify({ key, ...(vars || {}) });

// ── The fixture is the contract ─────────────────────────────────────────────

test('the sample fixture carries every key the renderer reads', () => {
  assert.deepEqual(Object.keys(SAMPLE.room).sort(),
    ['marker_pct', 'name', 'nr', 'page', 'polygon_pct', 'region_pct']);
  assert.equal(SAMPLE.ledger_available, true);
  SAMPLE.facts.forEach((f) => {
    assert.ok(FACT_ORDER.includes(f.key), `unknown fact key ${f.key}`);
    assert.ok(['read', 'assumed', 'missing'].includes(f.status));
    assert.ok(f.source && 'kind' in f.source && 'page' in f.source && 'rect_pct' in f.source);
    assert.equal(typeof f.sentence, 'string');
    assert.ok(f.editable.kind === 'number' || f.editable.kind === 'choice'
      || f.editable.kind === 'count');
  });
  SAMPLE.quantities.forEach((q) => {
    assert.ok(q.row_id && q.aprasymas && 'value' in q);
  });
});

// ── Fact ordering + status ──────────────────────────────────────────────────

test('orderFacts puts the six in sheet order regardless of payload order', () => {
  const shuffled = [...SAMPLE.facts].reverse();
  assert.deepEqual(orderFacts(shuffled).map((f) => f.key), [...FACT_ORDER]);
});

test('orderFacts keeps an unknown fact key, last and in payload order', () => {
  const withNew = [
    { key: 'sildymas' }, { key: 'grindys' }, { key: 'ventiliacija' }, { key: 'plotas' },
  ];
  assert.deepEqual(orderFacts(withNew).map((f) => f.key),
    ['plotas', 'grindys', 'sildymas', 'ventiliacija']);
});

test('orderFacts survives junk', () => {
  assert.deepEqual(orderFacts(null), []);
  assert.deepEqual(orderFacts([null, undefined]), []);
});

test('assumed and missing share the attention tone; read is plain', () => {
  assert.equal(factTone('read'), 'plain');
  assert.equal(factTone('assumed'), 'attention');
  assert.equal(factTone('missing'), 'attention');
  assert.equal(factNeedsInput({ status: 'assumed' }), true);
  assert.equal(factNeedsInput({ status: 'read' }), false);
});

test('an assumed fact prefills its default; a missing one opens empty', () => {
  assert.equal(prefillValue({ status: 'assumed', value: 2.8 }), '2,8',
    'the field must open with an LT decimal comma, like every other number');
  assert.equal(prefillValue({ status: 'read', value: 23.97 }), '23,97');
  assert.equal(prefillValue({ status: 'missing', value: 2.8 }), '');
  assert.equal(prefillValue({ status: 'read', value: null }), '');
  assert.equal(prefillValue({ status: 'read', value: 'parketas' }), 'parketas');
  assert.equal(prefillValue(null), '');
});

// ── Whole sheet vs a real rectangle ─────────────────────────────────────────

test('no rect means the crop is the whole sheet and must say so', () => {
  const aukstis = SAMPLE.facts.find((f) => f.key === 'aukstis');
  assert.equal(aukstis.source.rect_pct, null);
  assert.equal(isWholeSheet(aukstis), true);
});

test('a measured rectangle is not a whole sheet', () => {
  const plotas = SAMPLE.facts.find((f) => f.key === 'plotas');
  assert.equal(isWholeSheet(plotas), false);
});

test('a full-page rectangle counts as the whole sheet however it was spelled', () => {
  assert.equal(isWholeSheet({ source: { rect_pct: [0, 0, 1, 1] } }), true);
  assert.equal(isWholeSheet({ source: { rect_pct: [0.1, 0.1, 0.2, 0.2] } }), false);
  assert.equal(isWholeSheet({}), true);
});

// ── The walk ────────────────────────────────────────────────────────────────

const PROJECT = {
  v8_rooms: [
    { nr: '203', pavadinimas: 'Vonia', puslapio_nr: 3 },
    { nr: '101', pavadinimas: 'Tambūras', puslapio_nr: 2, user_verified_at: '2026-09-04T08:00:00Z' },
    { nr: '202', pavadinimas: 'Miegamasis', puslapio_nr: 3 },
    { nr: '20', pavadinimas: 'Sandėliukas', puslapio_nr: 3 },
  ],
  patalpos: [{ nr: '999', pavadinimas: 'Legacy' }],
};

test('rooms walk in drawing order: page first, then room number numerically', () => {
  assert.deepEqual(roomsInDrawingOrder(PROJECT).map((r) => r.nr),
    ['101', '20', '202', '203']);
});

test('an older blob without v8_rooms walks patalpos instead', () => {
  assert.deepEqual(roomsInDrawingOrder({ patalpos: PROJECT.patalpos }).map((r) => r.nr), ['999']);
  assert.deepEqual(roomsInDrawingOrder({ v8_rooms: [], patalpos: PROJECT.patalpos })
    .map((r) => r.nr), ['999']);
  assert.deepEqual(roomsInDrawingOrder({}), []);
});

test('rooms without a number are not walkable', () => {
  assert.deepEqual(roomsInDrawingOrder({ v8_rooms: [{ nr: null }, { nr: '' }, { nr: '5' }] })
    .map((r) => r.nr), ['5']);
});

test('roomTitle reads as the drawing prints it', () => {
  assert.equal(roomTitle({ nr: '110', pavadinimas: 'Miegamasis' }), '110 Miegamasis');
  assert.equal(roomTitle({ nr: '110' }), '110');
  assert.equal(roomTitle({ nr: '110', name: 'Vonia' }), '110 Vonia');
});

test('roomIndex finds a room whether the nr is a string or a number', () => {
  const rooms = roomsInDrawingOrder(PROJECT);
  assert.equal(roomIndex(rooms, '202'), 2);
  assert.equal(roomIndex(rooms, 202), 2);
  assert.equal(roomIndex(rooms, 'nope'), -1);
});

test('verification comes off the room stamp', () => {
  assert.equal(isRoomVerified({ user_verified_at: '2026-09-04T08:00:00Z' }), true);
  assert.equal(isRoomVerified({}), false);
});

// projectStore.markRoomVerified stamps `patalpos` only, and this walk reads
// `v8_rooms` first — so the second list has to be stamped too or the strip
// keeps reading „Patikrinta 0 iš 11" after a room has been verified.
test('the verification stamp can be mirrored onto the second room list', () => {
  const v8 = [{ nr: '101' }, { nr: '102', user_verified_at: 'x' }];
  const out = stampVerified(v8, '102', '2026-09-04T09:00:00Z');
  assert.equal(out[0].user_verified_at, undefined);
  assert.equal(out[1].user_verified_at, '2026-09-04T09:00:00Z');
  assert.notEqual(out[1], v8[1], 'must not mutate the stored room in place');
  assert.equal(stampVerified(v8, 102, 'z')[1].user_verified_at, 'z');
  assert.deepEqual(stampVerified(null, '1', 'z'), []);
  assert.deepEqual(stampVerified(v8, 'nope', 'z').map(isRoomVerified), [false, true]);
});

// ── Time estimate ───────────────────────────────────────────────────────────

test('the time left is 15 s per unchecked room, rounded up, never "0 min" mid-walk', () => {
  assert.equal(estimateMinutes(0), 0);
  assert.equal(estimateMinutes(1), 1);      // 15 s still reads as ~1 min
  assert.equal(estimateMinutes(4), 1);      // 60 s
  assert.equal(estimateMinutes(11), 3);     // 165 s → 3
  assert.equal(estimateMinutes(-5), 0);
});

test('progressSummary counts from the rooms themselves', () => {
  const s = progressSummary(roomsInDrawingOrder(PROJECT));
  assert.equal(s.total, 4);
  assert.equal(s.verified, 1);
  assert.equal(s.unchecked, 3);
  assert.equal(s.minutes, 1);
  assert.equal(s.percent, 25);
  assert.deepEqual(progressSummary([]),
    { total: 0, verified: 0, unchecked: 0, minutes: 0, percent: 0 });
});

// ── Corners from the outline ────────────────────────────────────────────────

test('a rectangle yields exactly four corners, K1..K4', () => {
  const corners = cornersFromPolygon([[0.2, 0.3], [0.4, 0.3], [0.4, 0.5], [0.2, 0.5]]);
  assert.equal(corners.length, 4);
  assert.deepEqual(corners.map((c) => c.label), ['K1', 'K2', 'K3', 'K4']);
});

test('collinear tracer points are not corners', () => {
  // The fixture ring has a mid-edge point on the top wall and a repeated close.
  const corners = cornersFromPolygon(SAMPLE.room.polygon_pct);
  assert.equal(corners.length, 4, 'a staircase of collinear points must not become 6 kampai');
});

test('an L-shaped room keeps its reflex corner', () => {
  const corners = cornersFromPolygon([
    [0.1, 0.1], [0.5, 0.1], [0.5, 0.3], [0.3, 0.3], [0.3, 0.6], [0.1, 0.6],
  ]);
  assert.equal(corners.length, 6);
});

test('no polygon means no corner dots — never a bounding box', () => {
  assert.deepEqual(cornersFromPolygon(null), []);
  assert.deepEqual(cornersFromPolygon([]), []);
  assert.deepEqual(cornersFromPolygon([[0.1, 0.1], [0.2, 0.2]]), []);
  assert.deepEqual(cornersFromPolygon([[0.1, 'x'], [null, 2]]), []);
});

test('corner terms are recognised so the dots can be highlighted', () => {
  const kampai = SAMPLE.quantities.find((q) => q.terms);
  assert.equal(hasCornerTerms(kampai.terms), true);
  assert.equal(hasCornerTerms({ perimetras: 12 }), false);
  assert.equal(hasCornerTerms(null), false);
});

test('termRows keeps the emitted order and drops non-numbers', () => {
  assert.deepEqual(termRows({ a: 1, b: null, c: 'x', d: 2 }),
    [{ label: 'a', value: 1 }, { label: 'd', value: 2 }]);
  assert.deepEqual(termRows(null), []);
});

// ── Placing an overlay on the returned crop ─────────────────────────────────
// Mirrors backend/api/evidence.py::_padded. The expected numbers below were
// confirmed against the live endpoint on 2026-09-04: returned pixel size ÷
// predicted padded size is the same page constant across five rects.

test('the crop is the requested rect grown by the pad, not the rect itself', () => {
  assert.deepEqual(paddedCropRect([0.2, 0.2, 0.4, 0.4]).map((v) => v.toFixed(4)),
    ['0.1880', '0.1880', '0.4120', '0.4120']);
  assert.deepEqual(paddedCropRect([0.4071, 0.5147, 0.6071, 0.7147]).map((v) => v.toFixed(4)),
    ['0.3951', '0.5027', '0.6191', '0.7267']);
});

test('a thin table row is grown to the legibility floor, centred', () => {
  const r = paddedCropRect([0.61, 0.34, 0.92, 0.36]);
  assert.deepEqual(r.map((v) => v.toFixed(4)), ['0.5980', '0.3275', '0.9320', '0.3725']);
  assert.ok(Math.abs((r[3] - r[1]) - CROP_MIN_H_PCT) < 1e-9, 'height floor');
});

test('a point-sized rect is grown to both floors', () => {
  const r = paddedCropRect([0.5, 0.5, 0.5, 0.5]);
  assert.ok(Math.abs((r[2] - r[0]) - CROP_MIN_W_PCT) < 1e-9);
  assert.ok(Math.abs((r[3] - r[1]) - CROP_MIN_H_PCT) < 1e-9);
});

test('a crop running off the sheet slides back in, it does not squash', () => {
  const r = paddedCropRect([0.0, 0.0, 0.2, 0.2]);
  assert.equal(r[0], 0);
  assert.equal(r[1], 0);
  // width is preserved (0.224), not clipped to 0.212
  assert.ok(Math.abs((r[2] - r[0]) - 0.224) < 1e-9);
  const far = paddedCropRect([0.9, 0.9, 1.0, 1.0]);
  assert.equal(far[2], 1);
  assert.ok(Math.abs((far[2] - far[0]) - 0.124) < 1e-9);
});

test('a full page asks for and gets the full page', () => {
  assert.deepEqual(paddedCropRect([0, 0, 1, 1]), [0, 0, 1, 1]);
});

test('paddedCropRect falls back to the whole page on junk', () => {
  assert.deepEqual(paddedCropRect(null), [0, 0, 1, 1]);
  assert.deepEqual(paddedCropRect([1, 2]), [0, 0, 1, 1]);
  assert.deepEqual(paddedCropRect(['a', 0, 1, 1]), [0, 0, 1, 1]);
  // a reversed rect is normalised, not rejected
  assert.deepEqual(paddedCropRect([0.4, 0.4, 0.2, 0.2]).map((v) => v.toFixed(4)),
    ['0.1880', '0.1880', '0.4120', '0.4120']);
});

test('a page point maps to its place inside the crop', () => {
  const crop = [0.2, 0.2, 0.6, 0.6];
  const mid = pageToCropPct([0.4, 0.4], crop);
  assert.equal(mid.inside, true);
  assert.ok(Math.abs(mid.x - 0.5) < 1e-9 && Math.abs(mid.y - 0.5) < 1e-9);
  assert.deepEqual(pageToCropPct([0.2, 0.2], crop), { x: 0, y: 0, inside: true });
});

test('a point outside the crop is reported, never clamped onto the edge', () => {
  const crop = [0.2, 0.2, 0.6, 0.6];
  const out = pageToCropPct([0.9, 0.4], crop);
  assert.equal(out.inside, false);
  assert.ok(out.x > 1, 'the real position is kept so the caller can decide');
  assert.equal(pageToCropPct([0.4, 0.4], [0.5, 0.5, 0.5, 0.5]).inside, false);
  assert.equal(pageToCropPct(null, crop).inside, false);
});

test('a polygon with nothing inside the crop yields no overlay at all', () => {
  const crop = [0.2, 0.2, 0.6, 0.6];
  assert.equal(polygonToCropPct([[0.9, 0.9], [0.95, 0.95]], crop), null);
  assert.equal(polygonToCropPct([], crop), null);
  assert.equal(polygonToCropPct(null, crop), null);
  const on = polygonToCropPct([[0.3, 0.3], [0.9, 0.9]], crop);
  assert.equal(on.length, 2);
  assert.equal(on[0].inside, true);
  assert.equal(on[1].inside, false);
});

// ── What may honestly be overridden ─────────────────────────────────────────

const ROWS = [
  {
    id: 'aaaa11112222',
    aprasymas: 'Sienų glaistymas/dažymas (iki 3m aukščio)',
    contributions_sum_to_total: true,
    contributions: [{ room_nr: '202', value: 48.2 }, { room_nr: '203', value: 32.0 }],
  },
  {
    id: 'bbbb33334444',
    aprasymas: 'Dažymo kampų montavimas',
    contributions_sum_to_total: true,
    contributions: [{ room_nr: '202', value: 44.8 }],
  },
  {
    id: 'cccc55556666',
    aprasymas: 'Grindjuosčių sumontavimas',
    contributions_sum_to_total: false,
    contributions: [{ room_nr: '202', value: 17.7 }],
  },
];

test('a row this room shares cannot be corrected from the room sheet', () => {
  const q = SAMPLE.quantities.find((x) => x.row_id === 'aaaa11112222');
  assert.equal(canOverrideWholeRow(q, ROWS, '202'), false);
});

test('a row only this room feeds may be corrected as a whole row', () => {
  const q = SAMPLE.quantities.find((x) => x.row_id === 'bbbb33334444');
  assert.equal(canOverrideWholeRow(q, ROWS, '202'), true);
});

test('a capped or anchored row is never overwritten from one room', () => {
  const q = SAMPLE.quantities.find((x) => x.row_id === 'cccc55556666');
  assert.equal(canOverrideWholeRow(q, ROWS, '202'), false,
    'contributions_sum_to_total:false means the room total is not what the line bills');
});

test('a sole contributor that is a DIFFERENT room is not this room to override', () => {
  const q = { row_id: 'bbbb33334444' };
  assert.equal(canOverrideWholeRow(q, ROWS, '203'), false);
});

test('an unknown row id is not overridable', () => {
  assert.equal(canOverrideWholeRow({ row_id: 'nope' }, ROWS, '202'), false);
  assert.equal(canOverrideWholeRow({}, ROWS, '202'), false);
  assert.equal(findRowForQuantity(ROWS, { row_id: 'bbbb33334444' }).id, 'bbbb33334444');
  assert.equal(findRowForQuantity(ROWS, {}), null);
});

// The ledger id and the id quantityOverride.js matches on are NOT the same.
// Real blobs carry `id` and no `_id`, so handing it a row_id updates nothing
// and looks identical to a saved edit.
test('the legacy override key is eil_nr-aprasymas, not the ledger id', () => {
  assert.equal(legacyRowKey({ id: 'abc123', eil_nr: 4, aprasymas: 'Dažymo kampų montavimas' }),
    '4-Dažymo kampų montavimas');
  assert.equal(legacyRowKey({ _id: 'rnk-9', eil_nr: 4, aprasymas: 'X' }), 'rnk-9');
  assert.equal(legacyRowKey(null), null);
});

test('an override is refused when the legacy key would hit two rows', () => {
  const twins = [
    { id: 'a', eil_nr: 7, aprasymas: 'Glaistymas' },
    { id: 'b', eil_nr: 7, aprasymas: 'Glaistymas' },
    { id: 'c', eil_nr: 8, aprasymas: 'Dažymas' },
  ];
  assert.equal(legacyKeyIsUnique(twins, twins[0]), false);
  assert.equal(legacyKeyIsUnique(twins, twins[2]), true);
  assert.equal(legacyKeyIsUnique(twins, null), false);
});

// ── Opening counts ──────────────────────────────────────────────────────────
// Shaped like a real room's `elementai`: two windows, two doors, one LED niche.

const ELEMENTAI = [
  { tipas: 'langas', kiekis: 1, plotis_mm: 2200, aukstis_mm: 2000, _exterior: true },
  { tipas: 'langas', kiekis: 1, plotis_mm: 1400, aukstis_mm: 2000, _exterior: true },
  { tipas: 'duris', kiekis: 1, plotis_mm: 900, aukstis_mm: 2100, _exterior: false },
  { tipas: 'nisa_LED', kiekis: 1, ilgis_m: 3.6, _niche_type: 'ceiling_led' },
];

test('a stepper moves the opening it belongs to, matched on tipas + both sizes', () => {
  const next = adjustOpeningCount(ELEMENTAI, { tipas: 'langas', plotis_mm: 1400, aukstis_mm: 2000 }, 1);
  assert.equal(next[0].kiekis, 1, 'the other window is untouched');
  assert.equal(next[1].kiekis, 2);
  assert.equal(next[2].kiekis, 1);
});

test('a LED niche is never decremented by a door or window stepper', () => {
  const next = adjustOpeningCount(ELEMENTAI, { tipas: 'duris', plotis_mm: 900, aukstis_mm: 2100 }, -1);
  assert.equal(next[2].kiekis, 0);
  assert.equal(next[3].kiekis, 1, 'nisa_LED must stay');
  assert.equal(next[3].tipas, 'nisa_LED');
});

test('a count never goes below zero', () => {
  const once = adjustOpeningCount(ELEMENTAI, { tipas: 'duris', plotis_mm: 900, aukstis_mm: 2100 }, -1);
  const twice = adjustOpeningCount(once, { tipas: 'duris', plotis_mm: 900, aukstis_mm: 2100 }, -1);
  assert.equal(twice[2].kiekis, 0);
});

test('only the first of two identical entries moves', () => {
  const twins = [
    { tipas: 'duris', kiekis: 1, plotis_mm: 900, aukstis_mm: 2100 },
    { tipas: 'duris', kiekis: 1, plotis_mm: 900, aukstis_mm: 2100 },
  ];
  const next = adjustOpeningCount(twins, twins[0], 1);
  assert.deepEqual(next.map((e) => e.kiekis), [2, 1]);
});

test('an unmatched detail changes nothing', () => {
  const next = adjustOpeningCount(ELEMENTAI, { tipas: 'langas', plotis_mm: 999, aukstis_mm: 1 }, 1);
  assert.deepEqual(next.map((e) => e.kiekis), [1, 1, 1, 1]);
  assert.deepEqual(adjustOpeningCount(null, {}, 1), []);
});

test('the openings total counts doors and windows, not niches', () => {
  assert.equal(countOpenings(ELEMENTAI), 3);
  assert.equal(countOpenings([]), 0);
  assert.equal(countOpenings(null), 0);
});

// ── Shared facts ────────────────────────────────────────────────────────────

const PAGES = [
  { nr: 1, tipas: 'title_page' },
  { nr: 2, tipas: 'floor_plan' },
  { nr: 4, tipas: 'plumbing' },
  { nr: 5, tipas: 'electrical' },
  { nr: 6, tipas: 'ceiling_plan' },
  { nr: 7, tipas: 'electrical' },
];

test('a symbol family is shown on the drawing it was counted on', () => {
  assert.equal(firstPageOfType(PAGES, symbolPageTypes('rozetes')), 5);
  assert.equal(firstPageOfType(PAGES, symbolPageTypes('klozetai')), 4);
  assert.equal(firstPageOfType(PAGES, symbolPageTypes('led_juostos')), 6);
});

test('a missing sheet falls back down the chain, never to a wrong one', () => {
  const noCeiling = PAGES.filter((p) => p.tipas !== 'ceiling_plan');
  assert.equal(firstPageOfType(noCeiling, symbolPageTypes('led_juostos')), 5);
  assert.equal(firstPageOfType([], symbolPageTypes('rozetes')), null);
  assert.equal(firstPageOfType(null, ['electrical']), null);
  assert.deepEqual(symbolPageTypes('nezinomas'), ['floor_plan']);
});

test('shared facts drop the zero counts — an absence is not a fact to check', () => {
  const rows = symbolRows({
    detected_symbols_summary: { rozetes: 52, radiatoriai: 0, klozetai: 2 },
    puslapiai: PAGES,
  });
  assert.deepEqual(rows.map((r) => r.key), ['rozetes', 'klozetai']);
  assert.deepEqual(rows.map((r) => r.page), [5, 4]);
  assert.deepEqual(symbolRows({}), []);
  assert.deepEqual(symbolRows({ detected_symbols_summary: 'nope' }), []);
});

test('a corrected symbol count is a whole number and never negative', () => {
  assert.deepEqual(setSymbolCount({ rozetes: 52 }, 'rozetes', 51), { rozetes: 51 });
  assert.deepEqual(setSymbolCount({ rozetes: 52 }, 'rozetes', -3), { rozetes: 0 });
  assert.deepEqual(setSymbolCount({ rozetes: 52 }, 'rozetes', 4.6), { rozetes: 5 });
  assert.deepEqual(setSymbolCount(null, 'rozetes', 2), { rozetes: 2 });
  assert.deepEqual(setSymbolCount({ a: 1 }, 'b', 'x'), { a: 1, b: 0 });
});

// ── The ripple ──────────────────────────────────────────────────────────────

const DIFF = {
  count: 3,
  deltaEur: 42.5,
  usePrices: true,
  changed: [
    { kind: 'changed', row: { aprasymas: 'Sienų dažymas', mato_vnt: 'm²' }, before: 40, after: 52.4 },
    { kind: 'changed', row: { aprasymas: 'Kampai', mato_vnt: 'm' }, before: 16.8, after: 18.0 },
    { kind: 'changed', row: { aprasymas: 'Lubų dažymas', mato_vnt: 'm²' }, before: 24, after: 24.001 },
  ],
};

test('the ripple headline is the biggest quantity move, in its own unit', () => {
  const s = summarizeRipple(DIFF);
  assert.equal(s.count, 3);
  assert.equal(s.top.aprasymas, 'Sienų dažymas');
  assert.equal(s.top.unit, 'm²');
  assert.ok(Math.abs(s.top.delta - 12.4) < 1e-9);
});

test('a move under half a hundredth is not a move', () => {
  const s = summarizeRipple({
    count: 1, changed: [{ row: { aprasymas: 'X', mato_vnt: 'm' }, before: 24, after: 24.001 }],
  });
  assert.equal(s.top, null);
});

test('summarizeRipple survives an empty or absent diff', () => {
  assert.deepEqual(summarizeRipple(null),
    { count: 0, deltaEur: 0, usePrices: false, top: null });
  assert.deepEqual(summarizeRipple({ count: 0, changed: [] }),
    { count: 0, deltaEur: 0, usePrices: false, top: null });
});

test('rippleText says nothing moved when nothing moved', () => {
  assert.equal(JSON.parse(rippleText({ count: 0, changed: [] }, stubT)).key,
    'project.roomSheet.rippleNone');
});

test('rippleText carries the LT plural, the sign and a comma decimal', () => {
  const out = JSON.parse(rippleText(DIFF, stubT));
  assert.equal(out.key, 'project.roomSheet.rippleTop');
  assert.equal(out.count, 3);
  assert.equal(out.rowsWord, 'eilutės');
  assert.equal(out.label, 'Sienų dažymas');
  assert.equal(out.delta, '+12,40 m²');
});

test('rippleText marks a shrink with a real minus sign, not a hyphen', () => {
  const out = JSON.parse(rippleText({
    count: 1, changed: [{ row: { aprasymas: 'Kampai', mato_vnt: 'm' }, before: 20, after: 16.8 }],
  }, stubT));
  assert.equal(out.delta, '−3,20 m');
  assert.equal(out.rowsWord, 'eilutė');
});

test('rows moved but no measurable delta still reports the row count', () => {
  const out = JSON.parse(rippleText({
    count: 11, changed: [{ row: { aprasymas: 'X' }, before: 1, after: 1 }],
  }, stubT));
  assert.equal(out.key, 'project.roomSheet.rippleRows');
  assert.equal(out.rowsWord, 'eilučių');
});


test('authorFigureRows pairs the designer\'s figure with OUR rows of the same family, summed, in the same unit', () => {
  const project = {
    _autoriaus_kiekiai: [
      { page: 3, label: 'Glaistoma dažoma (baltai)', value: 202, unit: 'm2', family: 'sienu_dazymas',
        bbox: [100, 200, 300, 212], page_width: 1000, page_height: 800 },
      { page: 8, label: 'Sienų plytelės - 60X120 cm', value: 38, unit: 'vnt', family: 'plyteles',
        bbox: [1, 2, 3, 4], page_width: 1000, page_height: 800 },
    ],
    darbu_sarasas: [
      { aprasymas: 'Sienų glaistymas/dažymas (iki 3m aukščio)', kiekis: 150.5, mato_vnt: 'm²' },
      { aprasymas: 'Sienų glaistymas/dažymas (virš 3m aukščio)', kiekis: 49.5, mato_vnt: 'm²' },
      { aprasymas: 'Lubų glaistymas/dažymas', kiekis: 94.03, mato_vnt: 'm²' },
      { aprasymas: 'Vonios sienų plytelių klijavimas', kiekis: 51.96, mato_vnt: 'm²' },
    ],
  };
  const rows = authorFigureRows(project);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].ours.value, 200);
  assert.equal(rows[0].ours.unit, 'm2');
  assert.equal(rows[0].group, null, 'one figure in the family → no group footer');
  assert.deepEqual(rows[0].rect, [0.08, 0.23, 0.32, 0.285]);
  assert.equal(rows[1].ours, null, 'a tile COUNT has no counterpart — we do not count tiles');
  assert.equal(rows[1].unit, 'vnt');
});

test('authorFigureRows: a family the designer split into parts is compared as a SUM, once', () => {
  const project = {
    _autoriaus_kiekiai: [
      { page: 3, label: 'Glaistoma dažoma (akcentinė)', value: 18, unit: 'm2', family: 'sienu_dazymas' },
      { page: 7, label: 'Plytelių klojimo', value: 3.95, unit: 'm2', family: 'plyteles' },
      { page: 3, label: 'Glaistoma dažoma (baltai)', value: 202, unit: 'm2', family: 'sienu_dazymas' },
      { page: 8, label: 'Sienų plytelės 60X120', value: 46, unit: 'm2', family: 'plyteles' },
    ],
    darbu_sarasas: [
      { aprasymas: 'Sienų glaistymas/dažymas', kiekis: 248.12, mato_vnt: 'm²' },
      { aprasymas: 'Vonios sienų plytelių klijavimas', kiekis: 51.96, mato_vnt: 'm²' },
      { aprasymas: 'Vonios grindų plytelių klijavimas', kiekis: 16.41, mato_vnt: 'm²' },
    ],
  };
  const rows = authorFigureRows(project);
  assert.deepEqual(rows.map((r) => r.value), [18, 202, 46, 3.95], 'paired families first, parts kept together');
  assert.deepEqual(rows[0].group, { size: 2, designerTotal: 220 });
  assert.equal(rows[1].group.designerTotal, 220);
  assert.equal(rows[0].ours.value, 248.12);
  assert.equal(rows[2].ours.value, 51.96, 'a tile label naming WALLS pairs with the wall tile rows only');
  assert.equal(rows[3].ours, null, 'a bare tile zone pairs with nothing');
});

test('authorFigureRows is empty when the backend read nothing, and never throws on junk', () => {
  assert.deepEqual(authorFigureRows({}), []);
  assert.deepEqual(authorFigureRows({ _autoriaus_kiekiai: [{ value: 'x' }, null] }), []);
  assert.equal(bboxToRectPct([1, 2, 3], 10, 10), null);
});


test('authorFigureRows: tile skirting pairs with the tile-skirting row, wooden skirting with the wooden one', () => {
  const project = {
    _autoriaus_kiekiai: [
      { page: 7, label: 'Grindjuostės (derinamos prie durų), h-8cm', value: 53.69, unit: 'm', family: 'grindjuostes' },
      { page: 7, label: 'Grindjuostės (iš plytelių), h-8cm', value: 24.97, unit: 'm', family: 'grindjuostes' },
    ],
    darbu_sarasas: [
      { aprasymas: 'Grindjuosčių sumontavimas', kiekis: 64.36, mato_vnt: 'm' },
      { aprasymas: 'Plytelių grindjuosčių supjovimas ir suklijavimas', kiekis: 8.42, mato_vnt: 'm' },
    ],
  };
  const rows = authorFigureRows(project);
  assert.equal(rows[0].ours.value, 64.36);
  assert.equal(rows[1].ours.value, 8.42);
  assert.equal(rows[0].group, null, 'two different skirtings are not one family total');
});
