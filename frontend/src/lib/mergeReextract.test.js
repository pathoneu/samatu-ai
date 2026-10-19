import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  carryUserFacts, factDiff, graftWallEvidence, mergeReextract, mergeReextractRooms, openingCounts,
  rereadDiffIsEmpty, rereadEntriesFor, roomTouched,
} from './mergeReextract.js';

const T = '2026-09-13T12:00:00.000Z';
const door = (n = 1) => ({ tipas: 'duris', plotis_mm: 900, aukstis_mm: 2100, kiekis: n });
const win = (n = 1) => ({ tipas: 'langas', plotis_mm: 1200, aukstis_mm: 1500, kiekis: n });

const oldRooms = () => ([
  { nr: '01', pavadinimas: 'Svetainė', paskirtis: 'gyvenamoji', plotas_m2: 37.86, perimetras_m: 36.56,
    perimetras_saltinis: 'user_override', lubu_aukstis_m: 2.82, elementai: [door(2), win(1)] },
  { nr: '02', pavadinimas: 'Miegamasis', paskirtis: 'miegamoji', plotas_m2: 14.26, perimetras_m: 18.29,
    lubu_aukstis_m: 2.82, elementai: [door(1), win(1)], user_verified_at: T },
  { nr: '03', pavadinimas: 'San. mazgas', paskirtis: 'san', plotas_m2: 3.52, perimetras_m: 8.3,
    lubu_aukstis_m: 2.82, elementai: [door(1)], _angos_user_at: T },
  { nr: '04', pavadinimas: 'Miegamasis 2', paskirtis: 'miegamoji', plotas_m2: 10.05, perimetras_m: 12.68,
    lubu_aukstis_m: 2.82, elementai: [door(1), win(1)] },
  { nr: '09', pavadinimas: 'Sandėliukas', paskirtis: 'sandeliukas', plotas_m2: 2.1, perimetras_m: 6.0,
    lubu_aukstis_m: 2.82, elementai: [door(1)] },
]);

const newRooms = () => ([
  { nr: '01', pavadinimas: 'Svetainė', paskirtis: 'gyvenamoji', plotas_m2: 37.86, perimetras_m: 27.5,
    perimetras_saltinis: 'vision', lubu_aukstis_m: 2.82, elementai: [door(3), win(1)],
    polygon_pct: [[0, 0], [1, 0], [1, 1]], polygon_source: 'sienu_konturas' },
  { nr: '02', pavadinimas: 'Miegamasis', paskirtis: 'miegamoji', plotas_m2: 14.26, perimetras_m: 18.9,
    lubu_aukstis_m: 2.82, elementai: [door(1), win(2)] },
  { nr: '03', pavadinimas: 'San. mazgas', paskirtis: 'san', plotas_m2: 3.52, perimetras_m: 8.3,
    lubu_aukstis_m: 2.82, elementai: [door(2)] },
  { nr: '04', pavadinimas: 'Miegamasis 2', paskirtis: 'miegamoji', plotas_m2: 10.4, perimetras_m: 12.68,
    lubu_aukstis_m: 2.82, elementai: [door(1), win(1)] },
  { nr: '05', pavadinimas: 'Skalbykla', paskirtis: 'skalbykla', plotas_m2: 3.76, perimetras_m: 8.89,
    lubu_aukstis_m: 2.82, elementai: [door(1)] },
]);

test('openings are counted by kind, hidden doors are doors', () => {
  assert.deepEqual(openingCounts([door(2), { tipas: 'pasleptos_duris' }, win(1)]), { durys: 3, langai: 1 });
  assert.deepEqual(openingCounts(undefined), { durys: 0, langai: 0 });
});

test('factDiff names what moved and nothing else', () => {
  const d = factDiff(oldRooms()[0], newRooms()[0]);
  assert.deepEqual(d.map((x) => x.key), ['perimetras_m', 'durys']);
  assert.deepEqual(d[0], { key: 'perimetras_m', from: 36.56, to: 27.5 });
  assert.deepEqual(factDiff(oldRooms()[3], oldRooms()[3]), []);
});

test('roomTouched sees every kind of his work', () => {
  assert.equal(roomTouched(oldRooms()[3]), false);
  assert.equal(roomTouched(oldRooms()[0]), true, 'a typed perimeter');
  assert.equal(roomTouched(oldRooms()[1]), true, 'a verified room');
  assert.equal(roomTouched(oldRooms()[2]), true, 'a corrected door count');
  assert.equal(roomTouched({ polygon_source: 'corrected' }), true);
  assert.equal(roomTouched({ plotas_source: 'manual_polygon' }), true);
  assert.equal(roomTouched({ _prideta_is_plano: true }), true);
  assert.equal(roomTouched({ grindu_danga: 'plyteles', grindu_danga_saltinis: 'user_override' }), true, 'a chosen floor covering');
  assert.equal(roomTouched({ grindu_danga: 'plyteles', grindu_danga_saltinis: 'grindu_planas' }), false, 'a covering the floor plan gave is not his work');
  assert.equal(roomTouched({ polygon_source: 'auto_floodfill' }), false, 'the reader\'s own polygon is not his');
});

test('carryUserFacts puts his facts back on the fresh read and lists the ones that differed', () => {
  const { room, carried } = carryUserFacts(oldRooms()[0], newRooms()[0]);
  assert.equal(room.perimetras_m, 36.56);
  assert.equal(room.perimetras_saltinis, 'user_override');
  assert.equal(room.polygon_source, 'sienu_konturas', 'the reader\'s new outline stays — he never drew one');
  assert.deepEqual(room.elementai, [door(3), win(1)], 'openings he never touched take the new read');
  assert.deepEqual(carried, [{ key: 'perimetras_m', kept: 36.56, read: 27.5 }]);

  const polyOld = { nr: '07', polygon_source: 'manual', polygon_pct: [[0, 0], [0, 1], [1, 1]], plotas_m2: 9.9,
    plotas_source: 'manual_polygon', page_nr: 2 };
  const polyNew = { nr: '07', polygon_source: 'sienu_konturas', polygon_pct: [[0, 0], [1, 0], [1, 1]],
    plotas_m2: 10.4, polygon_traced_at: 'x' };
  const c = carryUserFacts(polyOld, polyNew);
  assert.equal(c.room.polygon_source, 'manual');
  assert.deepEqual(c.room.polygon_pct, [[0, 0], [0, 1], [1, 1]]);
  assert.equal(c.room.plotas_m2, 9.9);
  assert.equal(c.room.polygon_traced_at, undefined, 'no key of the reader\'s polygon survives beside his');
  assert.deepEqual(c.carried.map((x) => x.key), ['plotas_m2', 'polygon']);

  const d = carryUserFacts(oldRooms()[2], newRooms()[2]);
  assert.deepEqual(d.room.elementai, [door(1)]);
  assert.deepEqual(d.carried, [{ key: 'durys', kept: 1, read: 2 }]);
});

test('a re-read keeps verified rooms and his facts, takes the rest, and says what it did', () => {
  const { rooms, diff } = mergeReextractRooms(oldRooms(), newRooms(), T);
  const by = Object.fromEntries(rooms.map((r) => [r.nr, r]));
  // 01: typed perimeter kept, new door count taken
  assert.equal(by['01'].perimetras_m, 36.56);
  assert.deepEqual(by['01'].elementai, [door(3), win(1)]);
  // 02: verified — every old fact stays, the read is only reported
  assert.equal(by['02'].perimetras_m, 18.29);
  assert.deepEqual(by['02'].elementai, [door(1), win(1)]);
  assert.equal(by['02'].user_verified_at, T);
  assert.equal(by['02']._reread_seen_at, T);
  // 03: corrected doors kept
  assert.deepEqual(by['03'].elementai, [door(1)]);
  // 04: untouched — the new read wins
  assert.equal(by['04'].plotas_m2, 10.4);
  // 05 new, 09 untouched and gone
  assert.ok(by['05'] && !by['09']);
  assert.equal(rooms.length, 5);

  assert.equal(diff.at, T);
  assert.deepEqual(diff.changed.map((c) => [c.nr, c.fields.map((f) => f.key)]),
    [['01', ['durys']], ['04', ['plotas_m2']]]);
  assert.deepEqual(diff.kept.map((k) => [k.nr, k.why, k.fields.map((f) => f.key)]),
    [['01', 'user', ['perimetras_m']], ['02', 'verified', ['perimetras_m', 'langai']], ['03', 'user', ['durys']]]);
  assert.deepEqual(diff.added, [{ nr: '05', pavadinimas: 'Skalbykla', plotas_m2: 3.76 }]);
  assert.deepEqual(diff.removed, [{ nr: '09', pavadinimas: 'Sandėliukas', plotas_m2: 2.1 }]);
  assert.equal(rereadDiffIsEmpty(diff), false);
});

test('a room he touched that the new read did not return stays and is listed', () => {
  const old = [{ nr: '08', pavadinimas: 'Holas', plotas_m2: 5.0, perimetras_m: 9.0, _prideta_is_plano: true,
    plotas_saltinis: 'plano_uzrasas' }];
  const { rooms, diff } = mergeReextractRooms(old, [], T);
  assert.equal(rooms.length, 1);
  assert.equal(rooms[0]._reread_missing_at, T);
  assert.deepEqual(diff.kept, [{ nr: '08', pavadinimas: 'Holas', why: 'missing', fields: [] }]);
  assert.deepEqual(diff.removed, []);
});

test('an identical second read produces an empty diff', () => {
  const { rooms, diff } = mergeReextractRooms(oldRooms().slice(3, 4), oldRooms().slice(3, 4), T);
  assert.equal(rooms.length, 1);
  assert.equal(rereadDiffIsEmpty(diff), true);
  assert.equal(rereadDiffIsEmpty(null), true);
});

test('mergeReextract keeps his project-level choices and prices, records the diff', () => {
  const base = {
    id: 'p1', name: 'Mano butas', company_name: 'UAB X', vat_rate: 21,
    patalpos: oldRooms(),
    _overrides: { lubu_auksciai: { '01': 2.82 } },
    _apimtis: { patalpos_ne: ['09'], darbai_ne: [] },
    _per_room_overrides: { '03': { tile_floor: true } },
    darbu_sarasas: [
      { aprasymas: 'Sienų glaistymas/dažymas', vnt: 'm2', kiekis: 220, kaina: 7.5 },
      { aprasymas: 'Grindjuosčių sumontavimas', vnt: 'm', kiekis: 53.69, kaina: 4 },
    ],
    _ceiling_anchor: { total_area_m2: 100 },
  };
  const result = {
    name: 'project.pdf', status: 'ok',
    patalpos: newRooms(),
    _overrides: { lubu_auksciai: { '01': 2.82 } },
    darbu_sarasas: [
      { aprasymas: 'Sienų glaistymas/dažymas', vnt: 'm2', kiekis: 231 },
      { aprasymas: 'Grindjuosčių sumontavimas', vnt: 'm', kiekis: 60 },
      { aprasymas: 'Lubų glaistymas/dažymas', vnt: 'm2', kiekis: 104 },
    ],
    _ceiling_anchor: { total_area_m2: 104.53 },
    _walls_anchor: { total_area_m2: 220 },
  };
  const { project, diff, notes } = mergeReextract(base, result, T);
  assert.equal(project.name, 'Mano butas');
  assert.equal(project.company_name, 'UAB X');
  assert.equal(project.vat_rate, 21);
  assert.deepEqual(project._apimtis, base._apimtis);
  assert.deepEqual(project._per_room_overrides, base._per_room_overrides);
  assert.equal(project._ceiling_anchor.total_area_m2, 104.53, 'the fresh read\'s own anchors are newer');
  assert.equal(project._walls_anchor.total_area_m2, 220);
  assert.equal(project.patalpos.length, 5);
  assert.deepEqual(project.v8_rooms, project.patalpos);
  const walls = project.darbu_sarasas.find((r) => r.aprasymas === 'Sienų glaistymas/dažymas');
  assert.equal(walls.kaina, 7.5, 'his price rides on the rebuilt row');
  assert.equal(walls.kiekis, 231, 'the quantity is the new one');
  assert.equal(project._reextracted_at, T);
  assert.equal(project._reread_diff, diff);
  assert.ok(Array.isArray(notes));
});

test('rereadEntriesFor hands the check sheet one room\'s share of the diff', () => {
  const { diff } = mergeReextractRooms(oldRooms(), newRooms(), T);
  assert.deepEqual(rereadEntriesFor(diff, '04'), { changed: [{ key: 'plotas_m2', from: 10.05, to: 10.4 }], kept: null });
  assert.deepEqual(rereadEntriesFor(diff, '02'),
    { changed: [], kept: { why: 'verified', fields: [{ key: 'perimetras_m', kept: 18.29, read: 18.9 }, { key: 'langai', kept: 1, read: 2 }] } });
  assert.equal(rereadEntriesFor(diff, '05'), null, 'a new room has no before');
  assert.equal(rereadEntriesFor(null, '01'), null);
});

test('a floor covering he chose survives a fresh read, and the difference is reported', () => {
  const old = { nr: '09', grindu_danga: 'plyteles', grindu_danga_saltinis: 'user_override' };
  const fresh = { nr: '09', grindu_danga: 'minksta', grindu_danga_saltinis: 'grindu_planas', _grindu_danga: { page: 7 } };
  const { room, carried } = carryUserFacts(old, fresh);
  assert.equal(room.grindu_danga, 'plyteles');
  assert.equal(room.grindu_danga_saltinis, 'user_override');
  assert.deepEqual(room._grindu_danga, { page: 7 }, 'what the floor plan draws stays beside his choice — the sheet says when they differ');
  assert.deepEqual(carried, [{ key: 'grindu_danga', kept: 'plyteles', read: 'minksta' }]);
  // the same covering read again is nothing to report
  assert.deepEqual(carryUserFacts(old, { nr: '09', grindu_danga: 'plyteles', grindu_danga_saltinis: 'grindu_planas' }).carried, []);
  // a covering the floor plan gave is simply replaced by the new read
  const planOnly = carryUserFacts({ nr: '09', grindu_danga: 'plyteles', grindu_danga_saltinis: 'grindu_planas' }, fresh);
  assert.equal(planOnly.room.grindu_danga, 'minksta');
});


// ── wall evidence (2026-10-16): `ilgis_pt` rides from the fresh read onto kept walls ─────────────
const eil = (text, page, line, extra = {}) => ({ text, value_m: Number(text) / 1000, page, line_pct: line, ...extra });
const L1 = [[0.39002, 0.40998], [0.4165, 0.40998]];
const L2 = [[0.1, 0.2], [0.1, 0.3]];
const storedWalls = () => ([
  { edge_pct: [[0, 0], [1, 0]], ilgis_m: 0.9, saltinis: 'eilute', kontrole_m: 0.91, istriza: false,
    eilutes: [eil('900', 1, L1)] },
  { edge_pct: [[1, 0], [1, 1]], ilgis_m: 1.384, saltinis: 'eilute', kontrole_m: 1.38, istriza: false,
    eilutes: [eil('1384', 1, L2), eil('1000', 1, [[0.5, 0.5], [0.6, 0.5]])] },
]);
const freshWalls = () => ([
  { edge_pct: [[0, 0], [1, 0]], ilgis_m: 0.9, saltinis: 'eilute', kontrole_m: 0.91, istriza: false,
    eilutes: [eil('900', 1, [[0.39052, 0.40948], [0.4162, 0.41]], { ilgis_pt: 22.14 })] },   // ends moved < 0.002
  { edge_pct: [[1, 0], [1, 1]], ilgis_m: 1.384, saltinis: 'eilute', kontrole_m: 1.38, istriza: false,
    eilutes: [eil('1384', 1, [...L2].reverse(), { ilgis_pt: 34.05 }),                        // drawn the other way
      eil('1001', 1, [[0.5, 0.5], [0.6, 0.5]], { ilgis_pt: 24.6 })] },                         // text no longer matches
]);

test('a verified room takes only the fresh strings\' ilgis_pt; every other key stays byte-identical', () => {
  const old = { nr: '05', pavadinimas: 'Svetainė', plotas_m2: 35.5, perimetras_m: 20.87,
    perimetras_saltinis: 'user_override', user_verified_at: T, _sienos: storedWalls(),
    _perimetras_suma: { suma_m: 20.87, sutampa: true } };
  const fresh = { nr: '05', pavadinimas: 'Svetainė', plotas_m2: 35.5, perimetras_m: 19.0,
    perimetras_saltinis: 'matmenu_eilutes', _sienos: freshWalls() };
  const before = JSON.stringify(old);
  const { rooms, diff } = mergeReextractRooms([old], [fresh], T);
  const r = rooms[0];
  assert.equal(JSON.stringify(old), before, 'the stored room object is not mutated');
  const strip = (x) => JSON.parse(JSON.stringify(x, (k, v) => (k === 'ilgis_pt' || k === '_reread_seen_at' ? undefined : v)));
  assert.deepEqual(strip(r), strip(old));
  const [[a], [b, c]] = r._sienos.map((w) => w.eilutes);
  assert.equal(a.ilgis_pt, 22.14);
  assert.equal(b.ilgis_pt, 34.05);
  assert.equal('ilgis_pt' in c, false, 'a string whose text no longer matches gets nothing');
  assert.deepEqual(a.line_pct, L1, 'the stored line stays the stored line');
  // the diff speaks of facts only — the graft is not a change
  assert.deepEqual(diff.changed, []);
  assert.deepEqual(diff.kept[0].fields.map((f) => f.key), ['perimetras_m']);
});

test('an unverified room behaves exactly as before (its walls come from the fresh read)', () => {
  const old = { nr: '01', plotas_m2: 6.0, perimetras_m: 6.85, perimetras_saltinis: 'matmenu_eilutes', _sienos: storedWalls() };
  const fresh = { nr: '01', plotas_m2: 6.0, perimetras_m: 6.85, perimetras_saltinis: 'matmenu_eilutes', _sienos: freshWalls() };
  const { rooms } = mergeReextractRooms([old], [fresh], T);
  assert.deepEqual(rooms[0], carryUserFacts(old, fresh).room);
  assert.deepEqual(rooms[0]._sienos, freshWalls());
});

test('graftWallEvidence returns the very same room when there is nothing to graft', () => {
  const kept = { nr: '1', _sienos: storedWalls() };
  assert.equal(graftWallEvidence(kept, { nr: '1' }), kept);
  assert.equal(graftWallEvidence({ nr: '1' }, { nr: '1', _sienos: freshWalls() }).nr, '1');
  const once = graftWallEvidence(kept, { _sienos: freshWalls() });
  assert.equal(graftWallEvidence(once, { _sienos: freshWalls() }), once, 'a second graft changes nothing');
});

test('carryUserFacts keeps the partition count he typed against a fresh read', () => {
  const old = { nr: '04', n_partition_walls: 3, n_partition_walls_saltinis: 'user_override', _n_partition_walls_user_at: '2026-10-17T10:00:00Z' };
  const fresh = { nr: '04', n_partition_walls: 5 };
  const { room, carried } = carryUserFacts(old, fresh);
  assert.equal(room.n_partition_walls, 3);
  assert.equal(room.n_partition_walls_saltinis, 'user_override');
  assert.equal(room._n_partition_walls_user_at, '2026-10-17T10:00:00Z');
  assert.deepEqual(carried.find((c) => c.key === 'n_partition_walls'), { key: 'n_partition_walls', kept: 3, read: 5 });
  // a count the program gave (no user source) is the fresh read's
  assert.equal(carryUserFacts({ nr: '04', n_partition_walls: 3 }, fresh).room.n_partition_walls, 5);
});

test('a door count answered on the question card stays answered through a re-read', () => {
  const old = { ...oldRooms()[2], _angos_patikrinta_at: T };
  const { room } = carryUserFacts(old, newRooms()[2]);
  assert.equal(room._angos_patikrinta_at, T);
  assert.deepEqual(room.elementai, old.elementai);
  assert.equal(carryUserFacts(oldRooms()[3], newRooms()[3]).room._angos_patikrinta_at, undefined);
});
