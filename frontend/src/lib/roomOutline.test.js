import test from 'node:test';
import assert from 'node:assert/strict';
import { displayPointOf, outlineFailureKey, roomsWithOutline } from './roomOutline.js';

const near = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} vs ${b}`);

test('a click arrives in unrotated page points and leaves as display-space page fractions', () => {
  const upright = displayPointOf({ x: 148.8, y: 210.5, pageIndex: 0, pageWidth: 595.2, pageHeight: 842, pageRotation: 0 });
  assert.equal(upright.page, 1);
  near(upright.x_pct, 0.25); near(upright.y_pct, 0.25);
  // a sheet stored sideways (/Rotate 90): the same place on the DISPLAYED sheet is elsewhere in its fractions
  const turned = displayPointOf({ x: 148.8, y: 210.5, pageIndex: 3, pageWidth: 595.2, pageHeight: 842, pageRotation: 1 });
  assert.equal(turned.page, 4);
  near(turned.x_pct, 0.75); near(turned.y_pct, 0.25);
});

test('a click without a page size, or off the sheet, is no click', () => {
  assert.equal(displayPointOf({ x: 10, y: 10, pageIndex: 0, pageWidth: 0, pageHeight: 842 }), null);
  assert.equal(displayPointOf({ x: -5, y: 10, pageIndex: 0, pageWidth: 595, pageHeight: 842 }), null);
  assert.equal(displayPointOf(null), null);
});

test('the answer patches ONLY geometry: null removes a key, the neighbours get their openings', () => {
  const project = { patalpos: [
    { nr: '01', pavadinimas: 'Tambūras', plotas_m2: 4.48, perimetras_m: 8.6, perimetras_saltinis: 'konturo_ivertis',
      _konturo_priezastis: 'nesutampa su lentele', _perimetras_priezastis: 'x', walls_paintable_m2: 20.1 },
    { nr: '02', pavadinimas: 'Katilinė', _angos_sienose: { page: 1, angos: [{ i: 'vidus', plotis_m: 0.64 }] } },
    { nr: '03', pavadinimas: 'Koridorius' },
  ] };
  const answer = {
    status: 'ok',
    room: { polygon_pct: [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]], polygon_source: 'corrected', _konturas: { page: 1, saltinis: 'parodyta' },
      _konturo_priezastis: null, perimetras_m: 6.77, perimetras_saltinis: 'konturo_ivertis', _perimetras_priezastis: '1 iš 4 sienų be matmens',
      pavadinimas: 'NEVER', plotas_m2: 99 },
    kitu_angos: { '02': { page: 1, angos: [{ i: '01', plotis_m: 0.64 }] }, 77: { page: 1, angos: [] } },
  };
  const rooms = roomsWithOutline(project, '01', answer);
  assert.equal(rooms.length, 3);
  const [one, two, three] = rooms;
  assert.equal(one.polygon_source, 'corrected');
  assert.equal(one.perimetras_m, 6.77);
  assert.equal('_konturo_priezastis' in one, false);
  assert.equal(one._perimetras_priezastis, '1 iš 4 sienų be matmens');
  assert.equal(one.pavadinimas, 'Tambūras', 'a name is not geometry');
  assert.equal(one.plotas_m2, 4.48, 'an area is not geometry');
  assert.equal(one.walls_paintable_m2, 20.1);
  assert.deepEqual(two._angos_sienose.angos, [{ i: '01', plotis_m: 0.64 }]);
  assert.equal(two.pavadinimas, 'Katilinė');
  assert.equal(three, project.patalpos[2], 'an untouched room is the same object');
  assert.equal(project.patalpos[0].perimetras_m, 8.6, 'the project is not mutated');
});

test('an answer that is not an outline patches nothing', () => {
  const project = { patalpos: [{ nr: '01' }] };
  assert.equal(roomsWithOutline(project, '01', { status: 'taken', nr: '02' }), null);
  assert.equal(roomsWithOutline(project, '01', null), null);
});

test('what a click may not do has its own sentence', () => {
  assert.deepEqual(outlineFailureKey({ status: 'taken', nr: '06' }), { key: 'outlineTaken', params: { room: '06' } });
  assert.deepEqual(outlineFailureKey({ status: 'open', plotas_m2: 37.77, su: ['05'] }), { key: 'outlineOpenWith', params: { rooms: '05', area: '37,77' } });
  assert.deepEqual(outlineFailureKey({ status: 'open', plotas_m2: 37.77, su: [] }), { key: 'outlineOpen', params: { area: '37,77' } });
  assert.deepEqual(outlineFailureKey({ status: 'outside' }), { key: 'outlineOutside', params: {} });
  assert.deepEqual(outlineFailureKey({ status: 'no_walls' }), { key: 'outlineNoWalls', params: {} });
  assert.deepEqual(outlineFailureKey({ status: 'whatever' }), { key: 'outlineFailed', params: {} });
});

// ── dividing a shared space with one line (2026-09-21) ──────────────────────
test('the answer of a split patches BOTH rooms, geometry only', async () => {
  const { roomsWithSplit } = await import('./roomOutline.js');
  const project = { patalpos: [
    { nr: '04', pavadinimas: 'Virtuvė', plotas_m2: 26.31, perimetras_m: 16.08, perimetras_saltinis: 'atviros_erdves_ivertis',
      _atvira_erdve: { nariai: ['04', '05'] }, walls_paintable_m2: 30.2 },
    { nr: '05', pavadinimas: 'Svetainė', plotas_m2: 35.5, perimetras_m: 21.69, _atvira_erdve: { nariai: ['04', '05'] } },
    { nr: '03', pavadinimas: 'Koridorius', _angos_sienose: { page: 1, angos: [{ i: 'vidus', plotis_m: 2.13 }] } },
  ] };
  const geometry = (p) => ({ polygon_pct: [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]], polygon_source: 'corrected', perimetras_m: p,
    perimetras_saltinis: 'konturo_ivertis', _atvira_erdve: null, _konturas: { page: 1, saltinis: 'padalinta', menamos: [[[0.2, 0.1], [0.2, 0.2]]] } });
  const answer = { status: 'ok', rooms: { '04': geometry(18.39), '05': geometry(19.38) },
    kitu_angos: { '03': { page: 1, angos: [{ i: '04', plotis_m: 2.13 }] } } };
  const rooms = roomsWithSplit(project, answer);
  assert.equal(rooms[0].perimetras_m, 18.39);
  assert.equal(rooms[1].perimetras_m, 19.38);
  assert.equal('_atvira_erdve' in rooms[0], false);
  assert.equal('_atvira_erdve' in rooms[1], false);
  assert.equal(rooms[0].pavadinimas, 'Virtuvė');
  assert.equal(rooms[0].plotas_m2, 26.31);
  assert.equal(rooms[0].walls_paintable_m2, 30.2);
  assert.deepEqual(rooms[2]._angos_sienose.angos, [{ i: '04', plotis_m: 2.13 }]);
  assert.equal(project.patalpos[0].perimetras_m, 16.08, 'the project is not mutated');
  assert.equal(roomsWithSplit(project, { status: 'bad_line' }), null);
});

test('why a line did not divide the space has its own sentence', async () => {
  const { splitFailureKey } = await import('./roomOutline.js');
  assert.deepEqual(splitFailureKey({ status: 'bad_line' }), { key: 'splitBadLine', params: {} });
  assert.deepEqual(splitFailureKey({ status: 'not_shared' }), { key: 'splitNotShared', params: {} });
  assert.deepEqual(splitFailureKey({ status: 'too_many' }), { key: 'splitTooMany', params: {} });
  assert.deepEqual(splitFailureKey({ status: 'no_walls' }), { key: 'outlineNoWalls', params: {} });
  assert.deepEqual(splitFailureKey({ status: '???' }), { key: 'outlineFailed', params: {} });
});

test('a split takes two clicks on ONE sheet', async () => {
  const { nextSplitClick } = await import('./roomOutline.js');
  const a = { page: 1, x_pct: 0.634, y_pct: 0.46 };
  const b = { page: 1, x_pct: 0.634, y_pct: 0.57 };
  assert.deepEqual(nextSplitClick(null, a), { first: a, request: null });
  assert.deepEqual(nextSplitClick(a, b), { first: null, request: { page: 1, a: { x_pct: 0.634, y_pct: 0.46 }, b: { x_pct: 0.634, y_pct: 0.57 } } });
  // a second click on ANOTHER sheet starts over there; a click on the same spot is not a line
  assert.deepEqual(nextSplitClick(a, { ...b, page: 6 }), { first: { ...b, page: 6 }, request: null });
  assert.deepEqual(nextSplitClick(a, { ...a }), { first: a, request: null });
  assert.deepEqual(nextSplitClick(a, null), { first: a, request: null });
});
