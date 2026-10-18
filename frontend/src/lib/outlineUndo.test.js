import test from 'node:test';
import assert from 'node:assert/strict';
import {
  mergePrevious, restorePatch, undoneRooms, undoneSentence, newerSaves, ticketFor, isNewest, UNDO_SUPERSEDED,
} from './outlineUndo.js';
import { saveOutlineTool } from './outlineToolSave.js';

const ring = [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]];
const union = [[0.1, 0.1], [0.4, 0.1], [0.4, 0.2], [0.1, 0.2]];

test('two answers of one split give one previous — the first answer wins where they overlap', () => {
  const a = { '01': { polygon_pct: ring, _konturas: null }, '03': { _angos_sienose: { a: 1 } } };
  const b = { '02': { polygon_pct: null }, '03': { _angos_sienose: { b: 2 } } };
  assert.deepEqual(mergePrevious(a, b, null, { x: 'not a room' }), {
    '01': { polygon_pct: ring, _konturas: null }, '03': { _angos_sienose: { a: 1 } }, '02': { polygon_pct: null },
  });
});

test('an undo answer lands as one patch: geometry and merge keys back, null keys removed, v8_rooms follow', () => {
  const merged = {
    patalpos: [
      { nr: '04', pavadinimas: 'Virtuvė', plotas_m2: 61.81, plotas_saltinis: 'eksplikacija_sujungta', polygon_pct: union, _sujungimas: { su: ['05'] } },
      { nr: '05', pavadinimas: 'Svetainė', plotas_m2: 35.5, _sujungta_i: '04', _konturas: { saltinis: 'sujungta', i: '04' } },
      { nr: '06', _angos_sienose: { now: true } },
    ],
    v8_rooms: [{ nr: '04' }, { nr: '05' }, { nr: '06' }],
  };
  const answer = {
    status: 'ok', atsaukta: 'sujungimas', kitu_angos: {},
    rooms: { '04': { polygon_pct: ring, _konturas: { saltinis: 'padalinta' } }, '05': { polygon_pct: ring, _konturas: { saltinis: 'padalinta' } }, '06': { _angos_sienose: null } },
    sujungimas: { '04': { plotas_m2: 26.31, plotas_saltinis: 'eksplikacija', _sujungimas: null }, '05': { plotas_m2: 35.5, _sujungta_i: null } },
  };
  const patch = restorePatch(merged, answer);
  const [r4, r5, r6] = patch.patalpos;
  assert.equal(r4.plotas_m2, 26.31);
  assert.equal(r4.plotas_saltinis, 'eksplikacija');
  assert.equal('_sujungimas' in r4, false);
  assert.deepEqual(r4.polygon_pct, ring);
  assert.equal(r4.pavadinimas, 'Virtuvė');                  // what the undo does not name stays
  assert.equal('_sujungta_i' in r5, false);
  assert.equal(r5._konturas.saltinis, 'padalinta');
  assert.equal('_angos_sienose' in r6, false);
  assert.equal(patch.v8_rooms[1], r5);
  assert.equal(restorePatch(merged, { status: 'taken' }), null);
});

test('the undo sentence names the rooms that changed back (not a neighbour whose openings did)', () => {
  const prev = { '05': { polygon_pct: null }, '04': { polygon_pct: ring }, '06': { _angos_sienose: null } };
  assert.deepEqual(undoneRooms(prev), ['04', '05']);
  assert.equal(undoneSentence('outline-merge', prev), 'Atšaukta: patalpos 04 ir 05 vėl atskiros');
  assert.equal(undoneSentence('outline-set', prev), 'Atšaukta: patalpų 04 ir 05 kontūrai grąžinti');
  assert.equal(undoneSentence('outline-set', { '06': { polygon_pct: ring } }), 'Atšaukta: patalpos 06 kontūras grąžintas');
});

test('an older save of a room cannot be undone after a newer one — it would drop the newer one silently', () => {
  const reg = newerSaves();
  const first = ticketFor(reg, ['04']);
  const other = ticketFor(reg, ['06']);
  assert.equal(isNewest(reg, first), true);
  const second = ticketFor(reg, ['04', '05']);
  assert.equal(isNewest(reg, first), false);
  assert.equal(isNewest(reg, second), true);
  assert.equal(isNewest(reg, other), true);
  assert.equal(isNewest(reg, null), false);
  assert.match(UNDO_SUPERSEDED, /naujesnį/);
});

test('every outline tool save hands its undo to the host: route, room and previous', async () => {
  const fresh = () => ({ patalpos: [{ nr: '01', polygon_pct: ring }, { nr: '02' }, { nr: '03' }] });
  const got = [];
  const onPrevious = (u) => got.push(u);
  const api = {
    outlineSet: async (nr, body) => ({ status: 'ok', room: { polygon_pct: body.polygon_pct }, previous: { [nr]: { polygon_pct: nr === '01' ? ring : null }, '03': { _angos_sienose: null } } }),
    outlineMerge: async () => ({ status: 'ok', rooms: { '01': { polygon_pct: union }, '02': { polygon_pct: null } }, sujungimas: {}, previous: { '01': { polygon_pct: ring, plotas_m2: 12 }, '02': { polygon_pct: null, plotas_m2: 9 } } }),
  };
  await saveOutlineTool({ kind: 'set', nr: '01', page: 1, polygon: union, holes: [] }, { api, getFresh: fresh, onPrevious });
  await saveOutlineTool({ kind: 'split', nr: '01', page: 1, polygon: ring, holes: [], other: { nr: '02', polygon: ring, holes: [] } }, { api, getFresh: fresh, onPrevious });
  await saveOutlineTool({ kind: 'merge', keptNr: '01', goneNr: '02', page: 1, polygon: union, holes: [] }, { api, getFresh: fresh, onPrevious });
  assert.deepEqual(got.map((u) => [u.action, u.nr, Object.keys(u.previous).sort()]), [
    ['outline-set', '01', ['01', '03']],
    ['outline-set', '01', ['01', '02', '03']],
    ['outline-merge', '02', ['01', '02']],
  ]);
  // without the callback nothing changes for the caller
  const patch = await saveOutlineTool({ kind: 'set', nr: '01', page: 1, polygon: union, holes: [] }, { api, getFresh: fresh });
  assert.deepEqual(patch.patalpos[0].polygon_pct, union);
});
