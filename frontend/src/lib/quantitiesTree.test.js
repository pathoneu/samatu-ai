import test from 'node:test';
import assert from 'node:assert/strict';
import {
  SORT_ALPHA, SORT_ORDER, SORT_QUANTITY, buildQuantitiesTree, familiesWithRoom, foldText,
  geometrySource, totalsByUnit, visibleRowKeys,
} from './quantitiesTree.js';

const POLY = [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]];

// Plan order: 01, 02, 03 — not alphabetical by name.
const ROOMS = [
  { nr: '01', pavadinimas: 'Tambūras', puslapio_nr: 2, polygon_pct: POLY, polygon_source: 'corrected' },
  { nr: '02', pavadinimas: 'Katilinė', puslapio_nr: 2, polygon_pct: POLY, polygon_source: 'vektoriniai_konturai' },
  { nr: '03', pavadinimas: 'Koridorius', puslapio_nr: 2, polygon_pct: POLY, polygon_source: 'auto_floodfill' },
];

const contribution = (nr, name, value, unit = 'm2') => ({
  room_nr: nr, room_name: name, page: 2, value, unit, included_because: 'Sienos dažomos', geometry: 'polygon',
});

// Shapes copied from the objektas_h blob: a summed line, an anchored line (Σ ≠ kiekis on purpose), a
// line with no per-room ledger, a line with no quantity yet.
const ROWS = [
  {
    id: 'walls', skyrius: 'Sienų glaistymas dažymas', aprasymas: 'Sienų glaistymas/dažymas',
    mato_vnt: 'm²', kiekis: 81.8, confidence: 'zalia',
    contributions: [contribution('02', 'Katilinė', 31.88), contribution('03', 'Koridorius', 49.92)],
    excluded: [{ room_nr: '01', room_name: 'Tambūras', excluded_because: 'Sienos neapdailinamos' }],
    roll_up: [{ op: 'sum', label: 'Σ 2 patalpų', value: 81.8 }],
    contributions_sum_to_total: true,
  },
  {
    id: 'corners', skyrius: 'Sienų glaistymas dažymas', aprasymas: 'Dažymo kampų montavimas',
    mato_vnt: 'm', kiekis: 120, confidence: 'geltona',
    contributions: [contribution('03', 'Koridorius', 70, 'm'), contribution('02', 'Katilinė', 50, 'm')],
    roll_up: [{ op: 'sum', label: 'Σ 2 patalpų', value: 120 }],
    contributions_sum_to_total: true,
  },
  {
    id: 'ceiling', skyrius: 'Lubų glaistymas dažymas', aprasymas: 'Lubų glaistymas/dažymas',
    mato_vnt: 'm²', kiekis: 143.27, confidence: 'zalia',
    contributions: [contribution('01', 'Tambūras', 4.48), contribution('02', 'Katilinė', 6.9)],
    roll_up: [{
      op: 'anchor', label: 'Eksplikacijos „BENDRAS PLOTAS"', value: 143.27,
      note: 'Bendras kiekis imamas iš eksplikacijos',
    }],
    contributions_sum_to_total: false,
  },
  {
    id: 'sockets', skyrius: 'Elektros instaliacijos darbai', aprasymas: 'Rozetės / jungiklio pajungimas',
    mato_vnt: 'vnt', kiekis: 75, confidence: 'geltona', saltinis: 'simboliai_brezinyje',
    contributions: [], roll_up: [],
  },
  {
    id: 'led', skyrius: 'GKP montavimas', aprasymas: 'LED nišos — suveskite ilgį',
    mato_vnt: 'm', kiekis: null, confidence: 'raudona', contributions: [], roll_up: [],
  },
];

test('one family per row, totals are the rows\' kiekis verbatim, sections keep server order', () => {
  const tree = buildQuantitiesTree(ROWS, ROOMS);
  assert.equal(tree.familyCount, 5);
  assert.deepEqual(tree.sections.map((s) => s.label), [
    'Sienų glaistymas dažymas', 'Lubų glaistymas dažymas', 'Elektros instaliacijos darbai', 'GKP montavimas',
  ]);
  assert.deepEqual(tree.families.map((f) => [f.id, f.total, f.unit]), [
    ['walls', 81.8, 'm²'], ['corners', 120, 'm'], ['ceiling', 143.27, 'm²'],
    ['sockets', 75, 'vnt'], ['led', null, 'm'],
  ]);
});

test('anchored line: total stays kiekis, rooms are detail, the roll_up line explains the gap', () => {
  const ceiling = buildQuantitiesTree(ROWS, ROOMS).families.find((f) => f.id === 'ceiling');
  assert.equal(ceiling.total, 143.27);
  assert.equal(ceiling.rooms.length, 2);
  assert.equal(ceiling.rollUpAuthoritative, true);
  assert.match(ceiling.rollUpLine, /BENDRAS PLOTAS/);
  assert.equal(ceiling.rollUpNote, 'Bendras kiekis imamas iš eksplikacijos');
  const walls = buildQuantitiesTree(ROWS, ROOMS).families.find((f) => f.id === 'walls');
  assert.equal(walls.rollUpAuthoritative, false);
  assert.equal(walls.rollUpLine, null);
});

test('room entries carry the server value, unit, geometry source, hidden flag and excluded rooms', () => {
  const walls = buildQuantitiesTree(ROWS, ROOMS, { hiddenRoomNrs: new Set(['03']) })
    .families.find((f) => f.id === 'walls');
  assert.deepEqual(walls.rooms.map((r) => [r.nr, r.value, r.unit, r.source.kind, r.hidden]), [
    ['02', 31.88, 'm²', 'walls', false], ['03', 49.92, 'm²', 'approx', true],
  ]);
  assert.equal(walls.rooms[0].room, ROOMS[1]);
  assert.deepEqual(walls.excluded, [{ nr: '01', name: 'Tambūras', because: 'Sienos neapdailinamos' }]);
});

test('a hand-typed quantity is flagged and keeps the program\'s own number for the explanation', () => {
  const typed = { ...ROWS[0], kiekis: 100, manual_override: true, ai_kiekis_original: 81.8 };
  const fam = buildQuantitiesTree([typed], ROOMS).families[0];
  assert.equal(fam.total, 100);
  assert.equal(fam.overridden, true);
  assert.equal(fam.programTotal, 81.8);
  assert.equal(fam.rooms.length, 2);
  assert.equal(buildQuantitiesTree(ROWS, ROOMS).families[0].overridden, false);
});

test('confidence normalizes through lib/confidence (legacy EN, unstamped)', () => {
  const tree = buildQuantitiesTree([
    { id: 'a', aprasymas: 'A', kiekis: 1, confidence: 'low' },
    { id: 'b', aprasymas: 'B', kiekis: 1 },
  ], []);
  assert.deepEqual(tree.families.map((f) => f.confidence), ['raudona', 'zalia']);
  assert.equal(tree.families[0].section, 'Kiti darbai');
});

test('geometrySource: user, walls, approximate, marker, none', () => {
  assert.equal(geometrySource(ROOMS[0]).label, 'pataisytas jūsų');
  assert.equal(geometrySource({ ...ROOMS[0], polygon_source: 'manual' }).kind, 'user');
  assert.equal(geometrySource({ polygon_source: 'sienu_konturas', polygon_pct: POLY }).label, 'kontūras iš sienų');
  assert.equal(geometrySource(ROOMS[2]).label, 'apytikslis');
  assert.equal(geometrySource({ marker_pct: [0.5, 0.5] }).kind, 'marker');
  assert.equal(geometrySource(null, { geometry: 'none' }).kind, 'none');
  // A user source without an outline is not a user outline.
  assert.equal(geometrySource({ polygon_source: 'corrected' }).kind, 'none');
});

test('sorting: room order by default, A–Ž and by quantity for both families and rooms', () => {
  const byOrder = buildQuantitiesTree(ROWS, ROOMS, { sort: SORT_ORDER });
  const corners = byOrder.families.find((f) => f.id === 'corners');
  assert.deepEqual(corners.rooms.map((r) => r.nr), ['02', '03']);

  const byQty = buildQuantitiesTree(ROWS, ROOMS, { sort: SORT_QUANTITY });
  assert.deepEqual(byQty.sections[0].families.map((f) => f.id), ['corners', 'walls']);
  assert.deepEqual(byQty.families.find((f) => f.id === 'walls').rooms.map((r) => r.nr), ['03', '02']);

  const byName = buildQuantitiesTree(ROWS, ROOMS, { sort: SORT_ALPHA });
  assert.deepEqual(byName.sections[0].families.map((f) => f.id), ['corners', 'walls']);
  assert.deepEqual(byName.families.find((f) => f.id === 'walls').rooms.map((r) => r.name),
    ['Katilinė', 'Koridorius']);
  // Sections never re-sort: they are the sąmata's own structure.
  assert.deepEqual(byName.sections.map((s) => s.label), byOrder.sections.map((s) => s.label));
});

test('filter: by line or section keeps all rooms; by room keeps only that room; diacritics ignored', () => {
  const byLine = buildQuantitiesTree(ROWS, ROOMS, { filter: 'dazymo kamp' });
  assert.deepEqual(byLine.families.map((f) => f.id), ['corners']);
  assert.equal(byLine.families[0].rooms.length, 2);
  assert.equal(byLine.families[0].matchedBy, 'family');

  const bySection = buildQuantitiesTree(ROWS, ROOMS, { filter: 'elektros' });
  assert.deepEqual(bySection.families.map((f) => f.id), ['sockets']);

  const byRoom = buildQuantitiesTree(ROWS, ROOMS, { filter: 'koridor' });
  assert.deepEqual(byRoom.families.map((f) => f.id), ['walls', 'corners']);
  assert.ok(byRoom.families.every((f) => f.rooms.length === 1 && f.rooms[0].nr === '03'));
  assert.equal(byRoom.families[0].matchedBy, 'room');
  // The family total never shrinks to the filtered rooms.
  assert.equal(byRoom.families[0].total, 81.8);

  const byNr = buildQuantitiesTree(ROWS, ROOMS, { filter: '01' });
  assert.deepEqual(byNr.families.map((f) => f.id), ['ceiling']);

  assert.equal(buildQuantitiesTree(ROWS, ROOMS, { filter: 'nėra tokio' }).sections.length, 0);
  assert.equal(foldText('  Dažymas ŠVIESA '), 'dazymas sviesa');
});

test('totalsByUnit sums displayed kiekis per unit and counts lines without one', () => {
  const tree = buildQuantitiesTree(ROWS, ROOMS);
  assert.deepEqual(tree.totals.units, [
    { unit: 'm²', value: 225.07, lines: 2 }, { unit: 'm', value: 120, lines: 1 },
    { unit: 'vnt', value: 75, lines: 1 },
  ]);
  assert.equal(tree.totals.missing, 1);
  assert.deepEqual(totalsByUnit([]), { units: [], missing: 0 });
});

test('the tree is rebuilt from props: a recompute that changes kiekis shows the new number', () => {
  const before = buildQuantitiesTree(ROWS, ROOMS).families[0].total;
  const after = buildQuantitiesTree([{ ...ROWS[0], kiekis: 90.1 }, ...ROWS.slice(1)], ROOMS).families[0].total;
  assert.equal(before, 81.8);
  assert.equal(after, 90.1);
});

test('visibleRowKeys walks open sections and expanded families; familiesWithRoom finds a room', () => {
  const tree = buildQuantitiesTree(ROWS, ROOMS);
  const walls = tree.families[0];
  const keys = visibleRowKeys(tree, {
    collapsedSections: new Set(['section-Lubų glaistymas dažymas']),
    expandedFamilies: new Set([walls.key]),
  });
  assert.deepEqual(keys.slice(0, 5).map((k) => k.kind), ['section', 'family', 'room', 'room', 'family']);
  assert.equal(keys[2].nr, '02');
  assert.ok(!keys.some((k) => k.key === tree.families.find((f) => f.id === 'ceiling').key));
  assert.deepEqual(familiesWithRoom(tree, '01'), [tree.families.find((f) => f.id === 'ceiling').key]);
  assert.deepEqual(familiesWithRoom(tree, null), []);
});

test('robust to junk: no rows, null rows, duplicate ids', () => {
  assert.equal(buildQuantitiesTree(null, null).sections.length, 0);
  const tree = buildQuantitiesTree([null, { id: 'x', aprasymas: 'X', kiekis: 1 }, { id: 'x', aprasymas: 'Y', kiekis: 2 }], []);
  assert.equal(tree.families.length, 2);
  assert.notEqual(tree.families[0].key, tree.families[1].key);
});
