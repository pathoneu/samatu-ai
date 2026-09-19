import test from 'node:test';
import assert from 'node:assert/strict';
import { buildCheckOverlay, focusRectFor, mapPct, wallLabel, wallState } from './checkOverlay.js';

const near = (a, b, eps = 1e-6) => assert.ok(Math.abs(a - b) < eps, `${a} vs ${b}`);

// objektas_h-shaped: the outline is traced on the layout sheet (1), the wall
// lengths are written on the wall-painting sheet (6), drawn 2 pt lower.
const SUT = {
  1: { base: 1, k: 1, kx: 1, ky: 1, dx_pct: 0, dy_pct: 0 },
  6: { base: 1, k: 1, kx: 1, ky: 1, dx_pct: 0, dy_pct: 0.0024 },
  8: { base: 8, k: 1, kx: 1, ky: 1, dx_pct: 0, dy_pct: 0 },
};
const OUTLINE = [[0.4, 0.25], [0.46, 0.25], [0.46, 0.38], [0.4, 0.38]];

const wall = (a, b, saltinis, texts, ilgis, page = 6) => ({
  page: 1, edge_pct: [a, b], ilgis_m: ilgis, saltinis, kontrole_m: 1.6,
  eilutes: texts.map((t) => ({ text: t, page, line_pct: [[a[0], a[1] + 0.004], [b[0], b[1] + 0.004]] })),
});

const room = { nr: '02', page: 1, polygon_pct: OUTLINE, marker_pct: [0.43, 0.31], region_pct: [0.4, 0.25, 0.46, 0.38] };
const perimetras = {
  key: 'perimetras', value: 12.17,
  source: { kind: 'planas', page: 6, rect_pct: [0.37, 0.22, 0.49, 0.41] },
  outline: { page: 1, polygon_pct: OUTLINE },
  walls: [
    wall([0.4, 0.25], [0.46, 0.25], 'eilute', ['1586'], 1.586),
    wall([0.46, 0.25], [0.46, 0.38], 'eilute', ['1200', '900', '2400'], 4.5),
    wall([0.46, 0.38], [0.4, 0.38], 'priesinga_siena', ['1586'], 1.586),
    { page: 1, edge_pct: [[0.4, 0.38], [0.4, 0.25]], ilgis_m: null, saltinis: null, kontrole_m: 4.5, eilutes: [] },
  ],
};
const plotas = { key: 'plotas', value: 6.9, source: { kind: 'eksplikacija', page: 1, rect_pct: [0.1, 0.55, 0.3, 0.56] } };
const aukstis = { key: 'aukstis', value: 2.82, source: { kind: 'prielaida', page: 1, rect_pct: [0.4, 0.25, 0.46, 0.38] } };

test('a point is laid onto another sheet of the same plan, and back', () => {
  const p = mapPct([0.4, 0.25], 1, 6, SUT);
  near(p[0], 0.4); near(p[1], 0.25 - 0.0024);
  const back = mapPct(p, 6, 1, SUT);
  near(back[0], 0.4); near(back[1], 0.25);
});

test('sheets of different plans, unknown sheets and the same sheet leave the point alone', () => {
  assert.deepEqual(mapPct([0.4, 0.25], 1, 8, SUT), [0.4, 0.25]);
  assert.deepEqual(mapPct([0.4, 0.25], 1, 3, SUT), [0.4, 0.25]);
  assert.deepEqual(mapPct([0.4, 0.25], 6, 6, SUT), [0.4, 0.25]);
  assert.deepEqual(mapPct([0.4, 0.25], 1, 6, null), [0.4, 0.25]);
});

test('a re-printed sheet at another scale maps through its factors', () => {
  const sut = { 1: SUT[1], 2: { base: 1, k: 2, kx: 2, ky: 2, dx_pct: -0.1, dy_pct: 0.05 } };
  const p = mapPct([0.3, 0.2], 2, 1, sut);
  near(p[0], 0.5); near(p[1], 0.45);
  const back = mapPct(p, 1, 2, sut);
  near(back[0], 0.3); near(back[1], 0.2);
});

test('a wall says where its length came from', () => {
  assert.equal(wallState(perimetras.walls[0]), 'read');
  assert.equal(wallState(perimetras.walls[2]), 'borrowed');
  assert.equal(wallState({ saltinis: 'konturas', ilgis_m: 0.15 }), 'outline');
  assert.equal(wallState(perimetras.walls[3]), 'missing');
  assert.equal(wallLabel(perimetras.walls[0]), '1586');
  assert.equal(wallLabel(perimetras.walls[1]), '1200 + 900 + 2400');
  assert.equal(wallLabel({ saltinis: 'konturas', ilgis_m: 0.15, eilutes: [] }), '0,15');
  assert.equal(wallLabel(perimetras.walls[3]), '—');
});

test('the room is drawn on its own sheet AND on the sheet its numbers are written on', () => {
  const o = buildCheckOverlay({ room, facts: [plotas, perimetras, aukstis], sutapdinimas: SUT, activeFactKey: null });
  assert.deepEqual(Object.keys(o.pages).sort(), ['1', '6']);
  assert.equal(o.pages[1].outline.length, 4);
  assert.equal(o.pages[1].walls.length, 4);
  assert.deepEqual(o.pages[1].walls.map((w) => w.state), ['read', 'read', 'borrowed', 'missing']);
  assert.equal(o.pages[1].strings.length, 0);                 // no number is written on the layout sheet
  // on sheet 6 everything sits 0,0024 higher (that sheet is drawn lower, so base → sheet subtracts)
  near(o.pages[6].outline[0][1], 0.25 - 0.0024);
  near(o.pages[6].walls[0].a[1], 0.25 - 0.0024);
  assert.equal(o.pages[6].strings.length, 5);                  // 1 + 3 + the borrowed wall's 1
  assert.equal(o.pages[6].strings[0].text, '1586');
  near(o.pages[6].strings[0].a[1], 0.254);                     // a string is already in its own sheet's fractions
});

test('a fact rectangle that is only the room itself is not a mark; a real place is', () => {
  const o = buildCheckOverlay({ room, facts: [plotas, perimetras, aukstis], sutapdinimas: SUT, activeFactKey: 'plotas' });
  assert.deepEqual(o.pages[1].marks.map((m) => [m.key, m.active]), [['plotas', true]]);
  assert.equal(o.pages[6].marks.length, 0);                    // the perimeter's frame on 6 is the outline's box
});

test('focus: the room by default, the active fact when it has a place', () => {
  const idle = buildCheckOverlay({ room, facts: [plotas, perimetras], sutapdinimas: SUT, activeFactKey: null });
  assert.equal(idle.roomFocus.page, 1);
  assert.ok(idle.roomFocus.rect[0] < 0.4 && idle.roomFocus.rect[2] > 0.46);
  assert.equal(idle.factFocus, null);
  const onPerimeter = buildCheckOverlay({ room, facts: [plotas, perimetras], sutapdinimas: SUT, activeFactKey: 'perimetras' });
  assert.equal(onPerimeter.factFocus.page, 6);
  assert.ok(onPerimeter.factFocus.rect[0] <= 0.37 && onPerimeter.factFocus.rect[3] >= 0.41);
  const noPlace = { key: 'grindys', source: { kind: 'prielaida', page: 1, rect_pct: null } };
  assert.equal(buildCheckOverlay({ room, facts: [noPlace], sutapdinimas: SUT, activeFactKey: 'grindys' }).factFocus, null);
});

test('an open plan member gets the shared outline, dashed, and no walls', () => {
  const shared = [[0.44, 0.43], [0.87, 0.43], [0.87, 0.69], [0.44, 0.69]];
  const member = { nr: '04', page: 1, polygon_pct: [[0.44, 0.45], [0.67, 0.45], [0.67, 0.67], [0.44, 0.67]], marker_pct: [0.57, 0.54] };
  const fact = { key: 'perimetras', value: null, source: { page: 1, rect_pct: [0.41, 0.4, 0.9, 0.72] },
    outline: { page: 1, polygon_pct: null, open_space: { nariai: ['04', '05'], polygon_pct: shared, perimetras_m: 37.77, page: 1 } }, walls: [] };
  const o = buildCheckOverlay({ room: member, facts: [fact], sutapdinimas: SUT, activeFactKey: null });
  assert.equal(o.pages[1].outline, null);
  assert.deepEqual(o.pages[1].openSpace.points, shared);
  assert.deepEqual(o.pages[1].openSpace.nariai, ['04', '05']);
  assert.equal(o.pages[1].walls.length, 0);
  assert.deepEqual(o.pages[1].marker, { x: 0.57, y: 0.54, nr: '04' });      // which part of the shared space is this room
  assert.ok(o.roomFocus.rect[0] < 0.44 && o.roomFocus.rect[2] > 0.87);
});

test('a room with no outline at all is its printed number, and says why', () => {
  const bare = { nr: '01', page: 1, polygon_pct: [[0.33, 0.39], [0.43, 0.39], [0.43, 0.48], [0.33, 0.48]], marker_pct: [0.429, 0.428],
    region_pct: [0.33, 0.39, 0.43, 0.48] };
  const fact = { key: 'perimetras', value: 8.6, source: { page: 1, rect_pct: [0.33, 0.39, 0.43, 0.48] }, outline: null, walls: [],
    outline_reason: 'nesutampa su lentele: kontūras 2,86 m², lentelė 4,48 m²' };
  const o = buildCheckOverlay({ room: bare, facts: [fact], sutapdinimas: SUT, activeFactKey: null });
  assert.equal(o.pages[1].outline, null);
  assert.deepEqual(o.pages[1].marker, { x: 0.429, y: 0.428, nr: '01' });
  assert.equal(o.outlineReason, 'nesutampa su lentele: kontūras 2,86 m², lentelė 4,48 m²');
  assert.equal(o.roomFocus.page, 1);
  assert.ok(o.roomFocus.rect[2] - o.roomFocus.rect[0] >= 0.1);              // a readable neighbourhood, not a dot
});

test('nothing to go on gives an empty overlay, not an exception', () => {
  const o = buildCheckOverlay({ room: null, facts: null, sutapdinimas: null, activeFactKey: null });
  assert.deepEqual(o.pages, {});
  assert.equal(o.roomFocus, null);
  assert.equal(o.factFocus, null);
});

test('focus rectangles are padded, clamped and never degenerate', () => {
  assert.deepEqual(focusRectFor([[0.4, 0.25], [0.46, 0.38]], 0.02), [0.38, 0.23, 0.48, 0.4]);
  const edge = focusRectFor([0.0, 0.0, 0.05, 0.05], 0.04);
  assert.ok(edge[0] === 0 && edge[1] === 0 && edge[2] > 0.05);
  const dot = focusRectFor([[0.5, 0.5]], 0.0);
  assert.ok(dot[2] - dot[0] >= 0.08 && dot[3] - dot[1] >= 0.08);
  assert.equal(focusRectFor(null), null);
});
