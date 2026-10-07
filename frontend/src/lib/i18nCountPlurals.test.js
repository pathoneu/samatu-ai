import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import i18next from 'i18next';
import { ltCount } from './ltPlural.js';

// Count strings through the real i18next and the real locale files (2026-10-07: the
// project cards read „85 eilučių", „71 eilučių"). Lithuanian has three forms on whole
// numbers — CLDR one / few / other — and i18next picks them; this test only says
// which word each count must end up with.
const HERE = dirname(fileURLToPath(import.meta.url));
const locale = (lng) => JSON.parse(readFileSync(join(HERE, `../i18n/${lng}.json`), 'utf8'));
async function tOf(lng) {
  const i18n = i18next.createInstance();
  await i18n.init({ lng, resources: { [lng]: { translation: locale(lng) } }, interpolation: { escapeValue: false } });
  return i18n.t.bind(i18n);
}
const lt = await tOf('lt');
const en = await tOf('en');

const COUNTS = [1, 2, 11, 21, 22, 85, 110];
const VARS = { area: '12,5', delta: '+5 €', sum: '10,00 €', rooms: '101' };
const EILUTE = ['eilutė', 'eilutės', 'eilučių'];
const PATALPA = ['patalpa', 'patalpos', 'patalpų'];
const PATALPAI = ['patalpai', 'patalpoms', 'patalpų'];

// 1 → one, 2 → few, 11 → other, 21 → one, 22 → few, 85 → few, 110 → other
const FORM = { 1: 0, 2: 1, 11: 2, 21: 0, 22: 1, 85: 1, 110: 2 };

const KEYS = [
  ['dashboard.card.rows', EILUTE],
  ['project.sanity.summary', PATALPA],
  ['project.interior.roomsCount', PATALPA],
  ['project.interior.listPositions', EILUTE],
  ['project.mainView.roomsBadge', PATALPA],
  ['project.mainView.worksBadge', EILUTE],
  ['project.detail.rows', EILUTE],
  ['project.patikra.rippleRows', EILUTE],
  ['project.patikra.toastRipple', EILUTE],
  ['project.patikra.toastRippleNoPrice', EILUTE],
  ['project.patikra.toastRippleNoPriceYet', EILUTE],
  ['project.questions.acceptAllRooms', PATALPAI],
  ['project.questions.answeredHeight', PATALPAI],
  ['project.questions.answeredNumbers', PATALPAI],
  ['project.questions.answeredChoices', PATALPAI],
  ['project.roomSheet.saveForAll', PATALPAI],
  ['shared.positionsSum', EILUTE],
  ['upload.stream.roomsIdentified', PATALPA],
  ['upload.stream.foundRooms', ['patalpą', 'patalpas', 'patalpų']],
];

test('lt: the project card says „1 eilutė", „2 eilutės", „11 eilučių" — never „85 eilučių"', () => {
  const card = (n) => lt('dashboard.card.rows', { count: n });
  assert.deepEqual(COUNTS.map(card), [
    '1 eilutė', '2 eilutės', '11 eilučių', '21 eilutė', '22 eilutės', '85 eilutės', '110 eilučių',
  ]);
  // the four cards on the founder's screen
  assert.deepEqual([85, 82, 71, 62].map(card), ['85 eilutės', '82 eilutės', '71 eilutė', '62 eilutės']);
  assert.equal(card(0), '0 eilučių');
  assert.equal(card(20), '20 eilučių');
});

test('lt: every count string takes the word its number needs', () => {
  for (const [key, words] of KEYS) {
    for (const n of COUNTS) {
      const out = lt(key, { count: n, ...VARS });
      const want = `${n} ${words[FORM[n]]}`;
      assert.ok(out.includes(want), `${key} @ ${n}: „${out}" should contain „${want}"`);
      assert.ok(!out.includes('{{'), `${key} @ ${n}: unfilled placeholder in „${out}"`);
    }
  }
});

test('lt: the room sentences keep their other numbers', () => {
  assert.equal(lt('project.sanity.summary', { count: 11, area: '154,9' }), '11 patalpų, 154,9 m²');
  assert.equal(lt('project.mainView.roomsBadge', { count: 21, area: '210,0' }), '21 patalpa · 210,0 m²');
  assert.equal(lt('upload.stream.foundRooms', { count: 3 }), 'Radau 3 patalpas');
  assert.equal(lt('project.patikra.toastRipple', { count: 1, delta: '+12 €' }), 'Perskaičiuota: 1 eilutė · +12 €');
});

test('i18next agrees with ltPlural on every count it renders', () => {
  for (const n of [0, ...COUNTS, 12, 19, 100, 101, 111, 1001]) {
    assert.equal(lt('dashboard.card.rows', { count: n }), ltCount(n, ...EILUTE), `n=${n}`);
  }
});

test('en: one row, many rows', () => {
  assert.equal(en('dashboard.card.rows', { count: 1 }), '1 row');
  assert.equal(en('dashboard.card.rows', { count: 21 }), '21 rows');
  assert.equal(en('project.sanity.summary', { count: 1, area: '9,0' }), '1 room, 9,0 m²');
  assert.equal(en('project.questions.answeredHeight', { count: 1, rooms: '101' }), 'Answered: ceiling height saved for 1 room (101).');
  assert.equal(en('upload.stream.foundRooms', { count: 11 }), 'Found 11 rooms');
});
