import test from 'node:test';
import assert from 'node:assert/strict';
import { buildCheckOverlay, centreDelta, focusRectFor, mapPct, wallLabel, wallState } from './checkOverlay.js';

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
  // dimension_sum rule (c), 2026-10-24: a length from the other strings on the axis — shown as its number
  assert.equal(wallState({ saltinis: 'grandine', ilgis_m: 3.05, eilutes: [] }), 'borrowed');
  assert.equal(wallLabel({ saltinis: 'grandine', ilgis_m: 3.05, eilutes: [] }), '3,05');
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

test('how far the view must still move for a place on the page to sit in its middle', () => {
  // Measured in the browser (2026-09-20): in a document of mixed sheet sizes the engine's own
  // zoom-to-area ignores that a narrower sheet is centred — a room on a portrait A3 among landscape
  // sheets landed ~420 px to the side. The correction is measured from the DOM, after the zoom.
  const page = { left: 100, top: -400, width: 2000, height: 3000 };     // the sheet as laid out on screen
  const view = { left: 300, top: 100, width: 700, height: 500 };        // the viewer's window
  const d = centreDelta(page, view, [0.4, 0.75, 0.6, 0.85]);
  assert.equal(d.dx, 100 + 0.5 * 2000 - (300 + 350));
  assert.equal(d.dy, -400 + 0.8 * 3000 - (100 + 250));
  assert.deepEqual(centreDelta(page, view, null), { dx: 0, dy: 0 });
  assert.deepEqual(centreDelta(null, view, [0, 0, 1, 1]), { dx: 0, dy: 0 });
  assert.deepEqual(centreDelta({ ...page, width: 0 }, view, [0, 0, 1, 1]), { dx: 0, dy: 0 });
});

// ── the openings the walls show (2026-09-20) ────────────────────────────────
const angos = {
  key: 'angos', value: 1, status: 'assumed',
  source: { kind: 'sienu_angos', page: 1, rect_pct: [0.37, 0.22, 0.49, 0.41] },
  openings: { page: 1, items: [
    { line_pct: [[0.46, 0.3], [0.46, 0.33]], plotis_m: 0.77, i: '03', lauko: false },
    { line_pct: [[0.41, 0.25], [0.44, 0.25]], plotis_m: 1.37, i: 'laukas', lauko: true },
  ] },
};

test('the openings in the walls are drawn on every sheet the room is drawn on, with their width', () => {
  const o = buildCheckOverlay({ room, facts: [perimetras, angos], sutapdinimas: SUT, activeFactKey: null });
  assert.deepEqual(o.pages[1].openings.map((g) => [g.label, g.outside, g.to]), [['0,77', false, '03'], ['1,37', true, 'laukas']]);
  assert.deepEqual(o.pages[1].openings[0].a, [0.46, 0.3]);
  // …laid onto the wall-painting sheet exactly like the outline
  near(o.pages[6].openings[0].a[1], 0.3 - 0.0024);
  near(o.pages[6].openings[0].b[1], 0.33 - 0.0024);
  assert.equal(o.pages[1].openings.every((g) => g.active === false), true);
});

test('the openings stand out while the door-and-window fact is the one being looked at', () => {
  const o = buildCheckOverlay({ room, facts: [perimetras, angos], sutapdinimas: SUT, activeFactKey: 'angos' });
  assert.equal(o.pages[1].openings.every((g) => g.active === true), true);
  assert.deepEqual(o.factFocus.page, 1);
});

test('a fact without wall openings draws none, and a broken one is skipped', () => {
  const none = buildCheckOverlay({ room, facts: [perimetras, { ...angos, openings: null }], sutapdinimas: SUT });
  assert.deepEqual(none.pages[1].openings, []);
  const broken = { ...angos, openings: { page: 1, items: [{ line_pct: [[0.4, 'x']], plotis_m: 0.8 }, angos.openings.items[0]] } };
  const o = buildCheckOverlay({ room, facts: [perimetras, broken], sutapdinimas: SUT });
  assert.equal(o.pages[1].openings.length, 1);
});

// ── a space divided by a person: the boundary is drawn, and it is not a wall (2026-09-21) ──
test('an imaginary boundary is drawn on every sheet the room is drawn on', () => {
  const divided = { ...perimetras, outline: { ...perimetras.outline, menamos: [[[0.46, 0.25], [0.46, 0.38]]] } };
  const o = buildCheckOverlay({ room, facts: [divided], sutapdinimas: SUT });
  assert.deepEqual(o.pages[1].imaginary, [{ a: [0.46, 0.25], b: [0.46, 0.38] }]);
  near(o.pages[6].imaginary[0].a[1], 0.25 - 0.0024);
  const plain = buildCheckOverlay({ room, facts: [perimetras], sutapdinimas: SUT });
  assert.deepEqual(plain.pages[1].imaginary, []);
});

test('the points he has clicked so far are shown on their sheet', () => {
  const o = buildCheckOverlay({ room, facts: [perimetras], sutapdinimas: SUT, pickPoints: [{ page: 6, x_pct: 0.5, y_pct: 0.3 }] });
  assert.deepEqual(o.pages[6].pickPoints, [{ x: 0.5, y: 0.3 }]);
  assert.deepEqual(o.pages[1].pickPoints, []);
});

// ── a wall whose chain had holes: the label adds up, what was not READ stands in brackets (2026-09-21) ──
test('a wall made of strings and a door nobody wrote shows every part in order', () => {
  const w = { saltinis: 'eilute', ilgis_m: 3.598, eilutes: [{ text: '660' }, { text: '1538' }],
    dalys: [{ text: '660' }, { anga_m: 1.4, i: '08' }, { text: '1538' }] };
  assert.equal(wallLabel(w), '660 + (1,40) + 1538');
  const pier = { saltinis: 'eilute', ilgis_m: 0.92, eilutes: [{ text: '0.800' }], dalys: [{ trumpa_m: 0.12 }, { text: '0.800' }] };
  assert.equal(wallLabel(pier), '(0,12) + 0.800');
  assert.equal(wallLabel({ saltinis: 'eilute', eilutes: [{ text: '3665' }], dalys: [] }), '3665');
});

// ── the boundary the PROGRAM proposes for a shared space, shown BEFORE it is accepted (2026-09-21) ──
test('a proposed boundary is drawn on its sheet: both outlines and the line, without touching what was read', async () => {
  const { buildCheckOverlay } = await import('./checkOverlay.js');
  const room = { nr: '04', page: 1, marker_pct: [0.3, 0.5] };
  const facts = [{ key: 'perimetras', outline: { page: 1, polygon_pct: null, open_space: { nariai: ['04', '05'], page: 1, polygon_pct: [[0.1, 0.1], [0.7, 0.1], [0.7, 0.5], [0.1, 0.5]] } }, walls: [] }];
  const proposal = {
    page: 1, line_pct: [[0.4, 0.1], [0.4, 0.5]],
    rooms: { '04': [[0.1, 0.1], [0.4, 0.1], [0.4, 0.5], [0.1, 0.5]], '05': [[0.4, 0.1], [0.7, 0.1], [0.7, 0.5], [0.4, 0.5]] },
  };
  const o = buildCheckOverlay({ room, facts, proposal });
  assert.deepEqual(o.pages[1].proposal.line, [[0.4, 0.1], [0.4, 0.5]]);
  assert.deepEqual(o.pages[1].proposal.outlines.map((x) => x.nr), ['04', '05']);
  assert.equal(o.pages[1].proposal.outlines[0].points.length, 4);
  assert.ok(o.pages[1].openSpace, 'the shared space stays drawn under it');
  // nothing to show → nothing drawn
  assert.equal(buildCheckOverlay({ room, facts }).pages[1].proposal, null);
  assert.equal(buildCheckOverlay({ room, facts, proposal: { page: 1, line_pct: null, rooms: {} } }).pages[1].proposal, null);
  // a proposed OUTLINE (the face the walls close around a room's number, 2026-09-23): one outline, no line
  const one = buildCheckOverlay({ room, facts, proposal: { page: 1, line_pct: null, rooms: { '01': [[0.39, 0.39], [0.46, 0.39], [0.46, 0.44], [0.39, 0.44]] } } });
  assert.equal(one.pages[1].proposal.line, null);
  assert.deepEqual(one.pages[1].proposal.outlines.map((x) => x.nr), ['01']);
  // …and the drawing opens on it when the room has no outline of its own
  const bare = buildCheckOverlay({ room: { ...room, nr: '01', polygon_pct: null, outline: null }, facts: [],
    proposal: { page: 1, line_pct: null, rooms: { '01': [[0.39, 0.39], [0.46, 0.39], [0.46, 0.44], [0.39, 0.44]] } } });
  assert.equal(bare.roomFocus.page, 1);
  assert.ok(bare.roomFocus.rect[0] <= 0.39 && bare.roomFocus.rect[2] >= 0.46 && bare.roomFocus.rect[2] - bare.roomFocus.rect[0] < 0.4, JSON.stringify(bare.roomFocus));
});

// ── a fact whose evidence is on ANOTHER sheet and has no place of its own there (2026-09-21) ──────
test('a fact read on another sheet of the same plan is looked at where the ROOM lies on that sheet', async () => {
  const { buildCheckOverlay } = await import('./checkOverlay.js');
  const room = { nr: '01', page: 4 };
  const outline = [[0.2, 0.2], [0.4, 0.2], [0.4, 0.5], [0.2, 0.5]];
  const facts = [
    { key: 'perimetras', outline: { page: 4, polygon_pct: outline }, walls: [] },
    { key: 'grindys', source: { page: 7, rect_pct: null } },           // „Grindų plane (7 psl.)…" — a sheet, no box
  ];
  const sutapdinimas = { 4: { base: 2, k: 1, kx: 1, ky: 1, dx_pct: 0, dy_pct: 0 }, 7: { base: 2, k: 1, kx: 1, ky: 1, dx_pct: 0.1, dy_pct: -0.05 } };
  const o = buildCheckOverlay({ room, facts, sutapdinimas, activeFactKey: 'grindys' });
  assert.equal(o.factFocus.page, 7);
  const [x0, y0, x1, y1] = o.factFocus.rect;
  assert.ok(x0 < 0.1 && x1 > 0.3 && y0 < 0.25 && y1 > 0.55, 'the room\'s box, shifted onto sheet 7');
  // sheets that are NOT one plan: the whole sheet, never a box from another frame
  const apart = buildCheckOverlay({ room, facts, sutapdinimas: { 4: sutapdinimas[4] }, activeFactKey: 'grindys' });
  assert.deepEqual(apart.factFocus, { page: 7, rect: [0, 0, 1, 1] });
  // a fact on the room's own sheet without a box keeps the room's focus (nothing changes)
  const own = buildCheckOverlay({ room, facts: [facts[0], { key: 'grindys', source: { page: 4, rect_pct: null } }], sutapdinimas, activeFactKey: 'grindys' });
  assert.equal(own.factFocus, null);
});
