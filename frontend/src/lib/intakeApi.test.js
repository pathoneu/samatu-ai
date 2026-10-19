// Pathon v3 W5-D D14 — several drawings into one project PDF, the sheets named after their files.
import test from 'node:test';
import assert from 'node:assert/strict';
import { combineUploads, combinedName, needsCombine, sheetOverridesFromNames } from './intakeApi.js';

const f = (name) => new File(['x'], name);

test('one PDF goes as it is; several files or a picture are combined first', () => {
  assert.equal(needsCombine([f('a.pdf')]), false);
  assert.equal(needsCombine([f('a.pdf'), f('b.pdf')]), true);
  assert.equal(needsCombine([f('foto.JPG')]), true);
  assert.equal(needsCombine([]), false);
  assert.equal(combinedName([f('Architektura.pdf'), f('Elektra.pdf'), f('x.png')]), 'Architektura ir dar 2.pdf');
  assert.equal(combinedName([f('foto.jpg')]), 'foto.pdf');
});

test('the server names become the sheet rail overrides', () => {
  assert.deepEqual(sheetOverridesFromNames({ 1: 'Elektra · 1', 2: ' foto ', x: 'no', 3: '' }),
    { 1: { name: 'Elektra · 1' }, 2: { name: 'foto' } });
});

test('combineUploads reads the PDF and the names; a refusal carries the server sentence', async () => {
  const meta = encodeURIComponent(JSON.stringify({ lapai: [{}, {}], pavadinimai: { 1: 'Elektra', 2: 'foto' } }));
  const ok = async () => new Response(new Blob(['%PDF-1.7']), { status: 200, headers: { 'x-pathon-lapai': meta } });
  const got = await combineUploads([f('Elektra.pdf'), f('foto.jpg')], { fetchImpl: ok });
  assert.equal(got.file.type, 'application/pdf');
  assert.equal(got.file.name, 'Elektra ir dar 1.pdf');
  assert.deepEqual(got.overrides, { 1: { name: 'Elektra' }, 2: { name: 'foto' } });
  assert.equal(got.pages, 2);
  const no = async () => new Response(JSON.stringify({ detail: 'Failo „x.dwg“ formato neatpažinau' }), { status: 400 });
  await assert.rejects(combineUploads([f('x.dwg'), f('a.pdf')], { fetchImpl: no }), /formato neatpažinau/);
});
