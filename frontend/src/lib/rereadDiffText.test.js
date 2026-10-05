import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  changedLine, keptLine, rereadDiffLines, rereadLinesEmpty, rereadRoomLines, rereadValue,
} from './rereadDiffText.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const LT = JSON.parse(readFileSync(join(HERE, '../i18n/lt.json'), 'utf8'));
const EN = JSON.parse(readFileSync(join(HERE, '../i18n/en.json'), 'utf8'));
const at = (dict, key) => key.split('.').reduce((n, k) => (n == null ? n : n[k]), dict);
/** i18next's t, as far as these lines use it: a dotted key, a defaultValue, {{value}}. */
const tOf = (dict) => (key, opts = {}) => {
  const raw = at(dict, key);
  const s = typeof raw === 'string' ? raw : (opts.defaultValue ?? key);
  return s.replace(/\{\{(\w+)\}\}/g, (_, k) => String(opts[k] ?? ''));
};
const t = tOf(LT);

const CODES = ['corrected', 'manual', 'sienu_konturas', 'vektoriniai_konturai', 'auto_floodfill',
  'synthesized_from_bbox', 'bbox_fallback', 'manual_needed'];

test('an outline is said by where it came from, never by its code', () => {
  for (const c of CODES) {
    const s = rereadValue('polygon', c, t);
    assert.ok(s && !s.includes(c) && !s.includes('_'), `${c} → ${s}`);
    assert.equal(typeof at(LT, `project.reread.outline.${c}`), 'string', `lt.json lacks outline.${c}`);
    assert.equal(typeof at(EN, `project.reread.outline.${c}`), 'string', `en.json lacks outline.${c}`);
  }
  assert.equal(rereadValue('polygon', 'corrected', t), 'jūsų pataisytas');
  // an origin the app has no word for is „another outline", not the code
  assert.equal(rereadValue('polygon', 'kazkoks_naujas', t), at(LT, 'project.reread.outline.other'));
  assert.equal(rereadValue('polygon', null, t), '—');
});

test('numbers, purposes and floor coverings read as words with units', () => {
  assert.equal(rereadValue('plotas_m2', 12.4, t), '12,40 m²');
  assert.equal(rereadValue('durys', 2, t), '2');
  assert.equal(rereadValue('paskirtis', 'vonia', t), 'Vonia');
  assert.equal(rereadValue('paskirtis', 'nezinoma_paskirtis', t), 'nezinoma_paskirtis');
  assert.equal(rereadValue('grindu_danga', 'plyteles', t), 'plytelės');
});

test('a kept outline the new read gives back unchanged is not a line — the reported „corrected (corrected)"', () => {
  assert.equal(keptLine({ key: 'polygon', kept: 'corrected', read: 'corrected' }, t), null);
  assert.equal(keptLine({ key: 'polygon', kept: 'corrected', read: 'sienu_konturas' }, t),
    'kontūras jūsų pataisytas (naujas skaitymas: rastas pagal sienas)');
});

test('a changed line whose two values read the same is not shown', () => {
  assert.equal(changedLine({ key: 'plotas_m2', from: 12.001, to: 12.004 }, t), null);
  assert.equal(changedLine({ key: 'plotas_m2', from: 12, to: 12.4 }, t), 'plotas 12,00 m² → 12,40 m²');
  assert.equal(changedLine({ key: 'durys', from: 1, to: 2 }, t), 'durys 1 → 2');
});

test('a room with nothing left to say drops out; a room the new read did not find stays', () => {
  const diff = {
    at: '2026-10-05T09:00:00Z',
    changed: [{ nr: '01', pavadinimas: 'Svetainė', fields: [{ key: 'plotas_m2', from: 20, to: 20.001 }] },
      { nr: '02', pavadinimas: 'Virtuvė', fields: [{ key: 'perimetras_m', from: 14, to: 15.5 }] }],
    kept: [{ nr: '03', pavadinimas: 'Vonia', why: 'user', fields: [{ key: 'polygon', kept: 'corrected', read: 'corrected' }] },
      { nr: '04', pavadinimas: 'WC', why: 'missing', fields: [] },
      { nr: '05', pavadinimas: 'Holas', why: 'user',
        fields: [{ key: 'polygon', kept: 'manual', read: 'corrected' }, { key: 'plotas_m2', kept: 6, read: 6.5 }] }],
    added: [],
    removed: [],
  };
  const lines = rereadDiffLines(diff, t);
  assert.deepEqual(lines.changed.map((r) => r.nr), ['02']);
  assert.deepEqual(lines.changed[0].lines, ['perimetras 14,00 m → 15,50 m']);
  assert.deepEqual(lines.kept.map((r) => r.nr), ['04', '05']);
  assert.deepEqual(lines.kept[1].lines, [
    'kontūras jūsų nubrėžtas (naujas skaitymas: jūsų pataisytas)',
    'plotas 6,00 m² (naujas skaitymas: 6,50 m²)']);
  assert.equal(rereadLinesEmpty(lines), false);
  const text = JSON.stringify(lines);
  for (const c of CODES) assert.ok(!text.includes(`"${c}"`) && !text.includes(` ${c} `), c);
});

test('a diff whose only line reads the same is empty — the banner then says nothing changed', () => {
  const diff = { changed: [], kept: [{ nr: '03', why: 'user', fields: [{ key: 'polygon', kept: 'corrected', read: 'corrected' }] }],
    added: [], removed: [] };
  assert.equal(rereadLinesEmpty(rereadDiffLines(diff, t)), true);
  assert.equal(rereadLinesEmpty(rereadDiffLines(null, t)), true);
});

test('the room note: only what reads differently, null when nothing does', () => {
  const diff = {
    changed: [{ nr: '01', fields: [{ key: 'durys', from: 1, to: 2 }] }],
    kept: [{ nr: '03', why: 'user', fields: [{ key: 'polygon', kept: 'corrected', read: 'corrected' }] },
      { nr: '01', why: 'verified', fields: [{ key: 'plotas_m2', kept: 10, read: 11 }] }],
  };
  assert.equal(rereadRoomLines(diff, '03', t), null);
  assert.deepEqual(rereadRoomLines(diff, ' 01 ', t), {
    changed: ['durys 1 → 2'],
    kept: { why: 'verified', lines: ['plotas 10,00 m² (naujas skaitymas: 11,00 m²)'] },
  });
  assert.equal(rereadRoomLines(diff, '', t), null);
});
