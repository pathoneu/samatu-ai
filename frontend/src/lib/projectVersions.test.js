import test from 'node:test';
import assert from 'node:assert/strict';
import {
  sourceLabel, versionTime, versionSize, versionRows, diffSections, fetchVersions, fetchVersionDiff, restoreVersion,
} from './projectVersions.js';

const NOW = Date.parse('2026-10-16T12:00:00Z');

test('every source has a Lithuanian label and an unknown one reads „Kita"', () => {
  for (const s of ['issaugota', 'perskaityta', 'lapas', 'klausimas', 'grazinta', 'kita']) {
    assert.match(sourceLabel(s), /^[A-ZĄČĘĖĮŠŲŪŽ]/);
    assert.doesNotMatch(sourceLabel(s), /_/);
  }
  assert.equal(sourceLabel('zzz'), 'Kita');
});

test('versionTime speaks Vilnius time: today, yesterday, else the date', () => {
  assert.equal(versionTime('2026-10-16T11:02:09Z', { now: NOW }), 'šiandien 14:02');
  assert.equal(versionTime('2026-10-15T08:00:00Z', { now: NOW }), 'vakar 11:00');
  assert.match(versionTime('2026-09-01T08:00:00Z', { now: NOW }), /^rugsėjo 1 d\. 11:00$/);
  assert.equal(versionTime('nonsense', { now: NOW }), '');
});

test('versionSize', () => {
  assert.equal(versionSize(54118), '53 KB');
  assert.equal(versionSize(512), '512 B');
  assert.equal(versionSize(0), '');
  assert.equal(versionSize(2.5 * 1024 * 1024), '2,5 MB');
});

test('versionRows keeps the server order and marks the current one', () => {
  const rows = versionRows([
    { id: 3, created_at: '2026-10-16T11:02:09Z', saltinis: 'grazinta', pavadinimas: 'Prieš grąžinant versiją nuo 2026-10-16 13:50', suspausta: 54118, dabartine: false },
    { id: 1, created_at: '2026-10-16T10:50:00Z', saltinis: 'issaugota', pavadinimas: null, suspausta: 54000, dabartine: true },
  ], { now: NOW });
  assert.deepEqual(rows.map((r) => [r.id, r.sourceText, r.current]), [[3, 'Prieš grąžinant', false], [1, 'Išsaugota', true]]);
  assert.equal(rows[1].title, '');
  assert.deepEqual(versionRows(null), []);
});

test('diffSections drops empty parts and keeps the server sentences', () => {
  const s = diffSections({
    patalpos: { pridetos: [], pasalintos: [{ text: 'Pašalinta: Patalpa 04 WC' }], pakeistos: [{ text: 'Patalpa 03 Vonia: perimetras 36,56 m → 38,10 m' }] },
    eilutes: { pridetos: [], istrintos: [], pakeistos: [] },
    prielaidos: { pakeistos: [{ text: 'Prielaida „dažymo klasė“: 2 → 3' }] },
  });
  assert.deepEqual(s.map((x) => x.key), ['patalpos', 'prielaidos']);
  assert.deepEqual(s[0].lines, ['Pašalinta: Patalpa 04 WC', 'Patalpa 03 Vonia: perimetras 36,56 m → 38,10 m']);
  assert.deepEqual(diffSections(undefined), []);
});

test('the API calls hit the versions routes and throw with the status', async () => {
  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    calls.push([url, init.method || 'GET']);
    if (url.endsWith('/restore')) return { ok: false, status: 404, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => ({ versions: [{ id: 1 }], sakiniai: [] }) };
  };
  assert.deepEqual(await fetchVersions('p 1'), [{ id: 1 }]);
  await fetchVersionDiff('p1', 7);
  await assert.rejects(restoreVersion('p1', 7), (e) => e.status === 404);
  assert.deepEqual(calls, [
    ['/api/projects/p%201/versions', 'GET'],
    ['/api/projects/p1/versions/7/diff/dabartine', 'GET'],
    ['/api/projects/p1/versions/7/restore', 'POST'],
  ]);
});
