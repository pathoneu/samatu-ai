import test from 'node:test';
import assert from 'node:assert/strict';
import { floorAreaTotal, isMergedAway } from './floorArea.js';

// demo-objektas_h's start state: 11 rooms, 143,27 m² — 04 = 26,31, 05 = 35,50.
const ROOMS = [
  { nr: '01', plotas_m2: 20.53 }, { nr: '02', plotas_m2: 6.9 }, { nr: '03', plotas_m2: 10.0 },
  { nr: '04', plotas_m2: 26.31 }, { nr: '05', plotas_m2: 35.5 }, { nr: '06', plotas_m2: 44.03 },
];
const before = ROOMS.reduce((s, r) => s + r.plotas_m2, 0);

/** What „Sujungti" 05 → 04 leaves: 04 bills both table rows, 05 keeps its own row and names 04. */
function merged(rooms) {
  return rooms.map((r) => {
    if (r.nr === '04') return { ...r, plotas_m2: 61.81, plotas_saltinis: 'eksplikacija_sujungta', _sujungimas: { su: ['05'] } };
    if (r.nr === '05') return { ...r, _sujungta_i: '04' };
    return r;
  });
}

test('the floor total is the same before and after a merge — the absorbed room is inside the kept one', () => {
  assert.equal(Math.round(floorAreaTotal(ROOMS) * 100) / 100, Math.round(before * 100) / 100);
  assert.equal(Math.round(floorAreaTotal(merged(ROOMS)) * 100) / 100, Math.round(before * 100) / 100);
  // the plain sum the header used to show: 35,50 m² twice
  const naive = merged(ROOMS).reduce((s, r) => s + r.plotas_m2, 0);
  assert.equal(Math.round((naive - floorAreaTotal(merged(ROOMS))) * 100) / 100, 35.5);
});

test('only a merged-away room is skipped — a room he chose not to count is still on its table row', () => {
  assert.equal(isMergedAway({ nr: '05', _sujungta_i: '04' }), true);
  assert.equal(isMergedAway({ nr: '04', _sujungimas: { su: ['05'] } }), false);
  assert.equal(isMergedAway({ nr: '03', _neskaiciuoti: true, _neskaiciuoti_kodel: 'pasirinkimas' }), false);
  assert.equal(isMergedAway(null), false);
});

test('missing, empty and non-numeric areas add nothing; no rooms is 0', () => {
  assert.equal(floorAreaTotal([{ nr: '01' }, { nr: '02', plotas_m2: null }, { nr: '03', plotas_m2: '7.5' }, null]), 7.5);
  assert.equal(floorAreaTotal(undefined), 0);
  assert.equal(floorAreaTotal([]), 0);
});
