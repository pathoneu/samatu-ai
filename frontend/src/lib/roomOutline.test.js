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
