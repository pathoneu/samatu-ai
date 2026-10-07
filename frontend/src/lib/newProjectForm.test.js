/**
 * lib/newProjectForm — the New Project form's four fields reach the project
 * whichever hand saves it (2026-10-07, seen live): a reading outlives Railway's
 * ~10 min stream cut, the SERVER saves the project, and it used to arrive named
 * after the PDF with no company, object or ceiling height. The stream request
 * now carries them as `project_meta`; the browser's own save reads the same.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  projectMeta, interiorStreamForm, metaToRestore,
  META_TEXT_MAX, CEILING_DEFAULT_MIN_M, CEILING_DEFAULT_MAX_M,
} from './newProjectForm.js';

const FORM = { name: 'Testo g. 1 butas', companyName: 'UAB Statyba', objektas: 'namas', ceilingHeight: '2,75' };

// ── the four fields ─────────────────────────────────────────────────────────

test('what he typed and chose becomes the four project fields', () => {
  assert.deepEqual(projectMeta(FORM), {
    name: 'Testo g. 1 butas',
    company_name: 'UAB Statyba',
    objektas_tipas: 'namas',
    lubu_aukstis_default_m: 2.75,
  });
});

test('an empty form keeps empty text and no height — each hand falls back itself', () => {
  assert.deepEqual(projectMeta({ name: '', companyName: '', objektas: 'butas', ceilingHeight: '' }),
    { name: '', company_name: '', objektas_tipas: 'butas' });
  assert.deepEqual(projectMeta(), { name: '', company_name: '' });
});

test('text is trimmed and cut to the inputs\' length', () => {
  const m = projectMeta({ name: '  Testo g. 1  ', companyName: 'x'.repeat(META_TEXT_MAX + 50) });
  assert.equal(m.name, 'Testo g. 1');
  assert.equal(m.company_name.length, META_TEXT_MAX);
  assert.equal(projectMeta({ name: '   ' }).name, '');
  assert.equal(projectMeta({ name: 42 }).name, '');
});

test('only the form\'s three objects are kept', () => {
  for (const o of ['butas', 'namas', 'komercines']) {
    assert.equal(projectMeta({ objektas: o }).objektas_tipas, o);
  }
  assert.equal('objektas_tipas' in projectMeta({ objektas: 'pilis' }), false);
});

test('the ceiling height is kept only where Nustatymai would accept it', () => {
  assert.equal(projectMeta({ ceilingHeight: '2.8' }).lubu_aukstis_default_m, 2.8);
  assert.equal(projectMeta({ ceilingHeight: String(CEILING_DEFAULT_MIN_M) }).lubu_aukstis_default_m, 2);
  assert.equal(projectMeta({ ceilingHeight: String(CEILING_DEFAULT_MAX_M) }).lubu_aukstis_default_m, 6);
  for (const bad of ['280', '1,5', '6,5', '0', '-2,8', 'abc', '2,8 m']) {
    assert.equal('lubu_aukstis_default_m' in projectMeta({ ceilingHeight: bad }), false, bad);
  }
});

// ── the stream request ──────────────────────────────────────────────────────

test('the stream form carries project_meta next to the file and the rules', () => {
  const file = new Blob(['%PDF-1.4'], { type: 'application/pdf' });
  const meta = projectMeta(FORM);
  const fd = interiorStreamForm(file, {
    interiorSubtype: 'naujas', rulesOverride: { apimtis: { lubos: 'ne_musu' } }, meta,
  });
  assert.equal(fd.getAll('files').length, 1);
  assert.equal(fd.get('interior_subtype'), 'naujas');
  assert.deepEqual(JSON.parse(fd.get('rules_override')), { apimtis: { lubos: 'ne_musu' } });
  assert.deepEqual(JSON.parse(fd.get('project_meta')), meta);
});

test('no rules, no meta → neither field is sent; the subtype defaults', () => {
  const fd = interiorStreamForm(new Blob(['%PDF-1.4']));
  assert.equal(fd.get('interior_subtype'), 'naujas');
  assert.equal(fd.has('rules_override'), false);
  assert.equal(fd.has('project_meta'), false);
});

// ── a project the server saved ──────────────────────────────────────────────

test('a server that applied the fields leaves nothing to restore', () => {
  const meta = projectMeta(FORM);
  const saved = { id: 'p1', ...meta, tipas: 'interjeras' };
  assert.deepEqual(metaToRestore(saved, meta), {});
});

test('a server that did not apply them: his name and the rest go back', () => {
  const meta = projectMeta(FORM);
  const saved = { id: 'p1', name: 'Visi techniniai 01.28', company_name: '' };
  assert.deepEqual(metaToRestore(saved, meta), meta);
});

test('nothing typed is nothing to restore — the server\'s fallback name stays', () => {
  const meta = projectMeta({ name: '', companyName: '', objektas: 'butas', ceilingHeight: '' });
  assert.deepEqual(metaToRestore({ name: 'planas', company_name: '', objektas_tipas: 'butas' }, meta), {});
  assert.deepEqual(metaToRestore(null, meta), {});
  assert.deepEqual(metaToRestore({ name: 'planas' }, null), {});
});
