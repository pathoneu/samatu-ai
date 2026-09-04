import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  FACT_ORDER, canOverrideWholeRow, cornersFromPolygon, estimateMinutes,
  factNeedsInput, factTone, findRowForQuantity, hasCornerTerms, isRoomVerified,
  isWholeSheet, orderFacts, prefillValue, progressSummary, rippleText,
  roomIndex, roomTitle, roomsInDrawingOrder, summarizeRipple, termRows,
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
  assert.equal(prefillValue({ status: 'assumed', value: 2.8 }), '2.8');
  assert.equal(prefillValue({ status: 'missing', value: 2.8 }), '');
  assert.equal(prefillValue({ status: 'read', value: null }), '');
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
