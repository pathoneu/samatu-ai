import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { SECTION_OF_FIELD, SETTINGS_SECTIONS, perRoomSplit, sectionForField, visibleRoomRows } from './settingsSections.js';
import { wordCount } from './viewerCoachMarks.js';
import { isBannedText } from './userText.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const lt = JSON.parse(readFileSync(join(HERE, '../i18n/lt.json'), 'utf8'));
const en = JSON.parse(readFileSync(join(HERE, '../i18n/en.json'), 'utf8'));
const panel = readFileSync(join(HERE, '../components/project/AssumptionsPanel.jsx'), 'utf8');

test('five sections, in the order of the brief, named in lt and en', () => {
  assert.deepEqual([...SETTINGS_SECTIONS], ['bendra', 'patalpos', 'angos', 'medziagos', 'pasirinkimai']);
  assert.deepEqual(SETTINGS_SECTIONS.map((s) => lt.project.settings.sections[s]),
    ['Bendra', 'Patalpos', 'Angos ir angokraščiai', 'Medžiagos ir pakuotės', 'Skaičiavimo pasirinkimai']);
  for (const s of SETTINGS_SECTIONS) assert.ok(en.project.settings.sections[s], s);
  for (const s of Object.values(SECTION_OF_FIELD)) assert.ok(SETTINGS_SECTIONS.includes(s), s);
});

test('every engine input the panel writes has a section (none removed, none renamed)', () => {
  const written = new Set();
  for (const m of panel.matchAll(/setOne\('([a-z_]+)'/g)) written.add(m[1]);
  for (const m of panel.matchAll(/field: '([a-z_]+)'/g)) written.add(m[1]);
  // the brief's list: nothing removed
  for (const f of ['glaistimo_lygis', 'santechnika_potinkinis', 'vidaus_durys_beapvadines', 'angokrasciai_apimtis',
    'led_nisu_ivertinimas', 'sienos_storis_m', 'lubu_auksciai', 'walls_paint_override', 'stretch_ceiling_override',
    'custom_windows', 'custom_doors']) {
    assert.ok(written.has(f), `${f} is still written by the panel`);
  }
  assert.match(panel, /setOne\(BAG_KEY/);
  assert.match(panel, /setOne\(BUCKET_KEY/);
  for (const f of written) assert.ok(sectionForField(f), `${f} → a section`);
});

test('a jump opens the section that holds the field; unknown fields open nothing', () => {
  assert.equal(sectionForField('lubu_auksciai'), 'patalpos');
  assert.equal(sectionForField('stretch_ceiling_override'), 'patalpos');
  assert.equal(sectionForField('glaistimo_lygis'), 'bendra');
  assert.equal(sectionForField('vidaus_durys_beapvadines'), 'angos');
  assert.equal(sectionForField('pakuote_maiso_kg'), 'medziagos');
  assert.equal(sectionForField('led_nisu_ivertinimas'), 'pasirinkimai');
  assert.equal(sectionForField('grindu_danga'), null);
  assert.equal(sectionForField(null), null);
  assert.equal(sectionForField('constructor'), null);
});

test('per-room: the value most rooms share, and only the rooms that differ', () => {
  const rooms = [{ nr: '01', h: 2.82 }, { nr: '02', h: 2.82 }, { nr: '03', h: 3.1 }, { nr: '04', h: 2.8200001 }];
  const s = perRoomSplit(rooms, (r) => r.h);
  assert.equal(s.common, 2.82);
  assert.deepEqual(s.differing.map((r) => r.nr), ['03']);
  assert.equal(s.allSame, false);
  const same = perRoomSplit(rooms.slice(0, 2), (r) => r.h);
  assert.equal(same.allSame, true);
  const bools = perRoomSplit([{ nr: 1, p: true }, { nr: 2, p: false }, { nr: 3, p: true }], (r) => r.p);
  assert.equal(bools.common, true);
  assert.deepEqual(bools.differing.map((r) => r.nr), [2]);
  assert.deepEqual(perRoomSplit([], () => 1), { common: null, differing: [], allSame: true });
  // a tie keeps the first room's value
  assert.equal(perRoomSplit([{ nr: 1, p: false }, { nr: 2, p: true }], (r) => r.p).common, false);
});

test('rows shown: the differing rooms, plus a room named by a jump or being edited, or all on request', () => {
  const rooms = [{ nr: '01' }, { nr: '02' }, { nr: '03' }];
  assert.deepEqual(visibleRoomRows(rooms, [{ nr: '03' }]).map((r) => r.nr), ['03']);
  assert.deepEqual(visibleRoomRows(rooms, [{ nr: '03' }], { also: ['01', null] }).map((r) => r.nr), ['01', '03']);
  assert.deepEqual(visibleRoomRows(rooms, [], { showAll: true }).map((r) => r.nr), ['01', '02', '03']);
  assert.deepEqual(visibleRoomRows(rooms, []), []);
});

test('each note is ONE sentence, plain words', () => {
  for (const [lang, dict] of [['lt', lt], ['en', en]]) {
    for (const [k, v] of Object.entries(dict.project.settings.notes)) {
      assert.equal((v.match(/[.!?](\s|$)/g) || []).length, 1, `${lang} ${k}: ${v}`);
      assert.ok(wordCount(v) <= 14, `${lang} ${k}: ${v}`);
      if (lang === 'lt') assert.equal(isBannedText(v), false, v);
    }
  }
});
