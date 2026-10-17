import test from 'node:test';
import assert from 'node:assert/strict';
import {
  displayWidthPt, dpiTier, overlayUrl, sheetInfo, editionLabel, listRevisions, uploadRevision, deleteRevision,
} from './pdfRevisions.js';

const REC = {
  id: 'abc', created_at: '2026-10-17T08:00:00Z', pavadinimas: 'Planas v2.pdf',
  pagal_sena: {
    1: { naujas_lapas: 1, budas: 'sienos', sutapimas: 0.829 },
    2: { naujas_lapas: 2, budas: 'sienos', sutapimas: 0.954, geriausias: { old_page: 1, sutapimas: 1 } },
    5: { naujas_lapas: 6, budas: 'lapo_krastai', sutapimas: null, geriausias: { old_page: 4, sutapimas: 0.42 } },
  },
};

test('displayWidthPt swaps the box on quarter-turned sheets', () => {
  assert.equal(displayWidthPt({ width: 595, height: 842 }, 0), 595);
  assert.equal(displayWidthPt({ width: 595, height: 842 }, 90), 842);
  assert.equal(displayWidthPt({ width: 595, height: 842 }, 3), 842);
  assert.equal(displayWidthPt(null, 0), null);
});

test('dpiTier picks the smallest tier at least as sharp as the screen, capped at 150', () => {
  assert.equal(dpiTier(595, 595), 72);
  assert.equal(dpiTier(700, 595), 96);
  assert.equal(dpiTier(1100, 595), 150);
  assert.equal(dpiTier(5000, 595), 150);
  assert.equal(dpiTier(0, 595), 72);
});

test('overlayUrl defaults an unknown mode to skirtumas', () => {
  assert.equal(overlayUrl('p 1', 'abc', 2, 'naujas', 96), '/api/projects/p%201/pdf-revisions/abc/overlay/2?mode=naujas&dpi=96');
  assert.match(overlayUrl('p1', 'abc', 2, 'blend', 96), /mode=skirtumas/);
});

test('sheetInfo says how each sheet was laid, in plain words', () => {
  const a = sheetInfo(REC, 1);
  assert.equal(a.byWalls, true);
  assert.equal(a.text, 'Ant šio lapo — naujo leidimo lapas 1, sulygiuotas pagal sienas (sutapimas 0,83).');
  assert.match(sheetInfo(REC, 2).text, /panašus ir į lapą 1 \(1,00\) — palikta pagal lapo numerį/);
  const c = sheetInfo(REC, 5);
  assert.equal(c.byWalls, false);
  assert.match(c.text, /tik pagal lapo kraštus/);
  assert.match(c.text, /su lapu 4 \(0,42\) — per mažai/);
  assert.deepEqual(sheetInfo(REC, 9), { matched: false, newPage: null, byWalls: false, text: 'Šiam lapui naujame leidime atitikmens nėra.' });
  assert.equal(sheetInfo(null, 1), null);
});

test('editionLabel', () => {
  assert.equal(editionLabel(REC), 'Planas v2.pdf · spalio 17 d.');
  assert.equal(editionLabel({ created_at: 'x' }), 'Naujas leidimas');
});

test('API calls: list, upload as multipart, delete; errors carry the server sentence', async () => {
  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    calls.push([url, init.method || 'GET', init.body instanceof FormData]);
    if (init.method === 'DELETE') return { ok: false, status: 404, json: async () => ({ detail: 'Tokio brėžinio leidimo nėra' }) };
    return { ok: true, status: 200, json: async () => ({ leidimai: [REC], leidimas: REC }) };
  };
  assert.deepEqual(await listRevisions('p1'), [REC]);
  assert.equal((await uploadRevision('p1', new Blob(['%PDF']))).leidimas.id, 'abc');
  await assert.rejects(deleteRevision('p1', 'abc'), (e) => e.status === 404 && e.message === 'Tokio brėžinio leidimo nėra');
  assert.deepEqual(calls, [
    ['/api/projects/p1/pdf-revisions', 'GET', false],
    ['/api/projects/p1/pdf-revisions', 'POST', true],
    ['/api/projects/p1/pdf-revisions/abc', 'DELETE', false],
  ]);
});
