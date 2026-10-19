import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  FIRST_USE_IDS, FIRST_USE_KEY, FIRST_USE_PANELS, FIRST_USE_TOOLS, firstUseSeen, firstUseToolFor, markFirstUseSeen, resetFirstUse,
} from './firstUseHints.js';
import { CURSOR_HINT_MODES } from './cursorHints.js';
import { legendCursorHint, reviewOutcome } from './legendReview.js';
import { wordCount, COACH_MAX_WORDS } from './viewerCoachMarks.js';
import { isBannedText } from './userText.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const lt = JSON.parse(readFileSync(join(HERE, '../i18n/lt.json'), 'utf8'));
const en = JSON.parse(readFileSync(join(HERE, '../i18n/en.json'), 'utf8'));

const memStore = () => {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k) };
};

test('the brief\'s seven: G, R, X, Kiekis, Matavimai, a Patikra question card, Nustatymai', () => {
  assert.deepEqual([...FIRST_USE_IDS].sort(), ['count', 'legend', 'matavimai', 'nustatymai', 'patikra', 'room', 'subtract'].sort());
  for (const mode of Object.keys(FIRST_USE_TOOLS)) assert.ok(CURSOR_HINT_MODES.includes(mode), `${mode} is a cursor-hint mode`);
  for (const p of FIRST_USE_PANELS) assert.ok(p.anchor.startsWith('[data-testid'), p.id);
});

test('each hint is ONE short sentence in lt and en, no pipeline words', () => {
  for (const [lang, dict] of [['lt', lt], ['en', en]]) {
    for (const id of FIRST_USE_IDS) {
      const s = dict.project.firstUse[id];
      assert.ok(s, `${lang} ${id}`);
      assert.ok(wordCount(s) <= COACH_MAX_WORDS, `${lang} ${id}: ${s}`);
      assert.equal((s.match(/[.!?](\s|$)/g) || []).length, 1, `${lang} ${id}: ${s}`);
      if (lang === 'lt') assert.equal(isBannedText(s), false, s);
    }
  }
});

test('shown once: used up per id, remembered under one key; reset brings them back', () => {
  const s = memStore();
  assert.equal(firstUseSeen('legend', s), false);
  markFirstUseSeen('legend', s);
  assert.equal(firstUseSeen('legend', s), true);
  assert.equal(firstUseSeen('room', s), false);
  markFirstUseSeen('legend', s);
  assert.deepEqual(JSON.parse(s.getItem(FIRST_USE_KEY)), ['legend']);
  resetFirstUse(s);
  assert.equal(firstUseSeen('legend', s), false);
});

test('broken or garbage storage never nags', () => {
  const broken = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); }, removeItem() { throw new Error('x'); } };
  assert.equal(firstUseSeen('room', broken), true);
  assert.doesNotThrow(() => markFirstUseSeen('room', broken));
  const garbage = memStore();
  garbage.setItem(FIRST_USE_KEY, '{not json');
  assert.equal(firstUseSeen('room', garbage), true);
});

test('G: the first-use line points at the outcome, never repeats the legend tool\'s own sentences (B1-B)', () => {
  const g = lt.project.firstUse.legend;
  for (const phase of ['suggesting', 'proposed', 'box', 'reading', 'counting', 'review', 'creating']) {
    assert.notEqual(legendCursorHint(phase), g, phase);
  }
  const outcomes = [reviewOutcome({ rows: [] }), reviewOutcome({ countError: 'x' })];
  for (const o of outcomes) assert.ok(!o.text.includes(g) && o.short !== g);
  assert.match(g, /ženklų skaičiumi/);
});

test('only the four tools have a cursor first-use line', () => {
  assert.equal(firstUseToolFor('legend'), 'legend');
  assert.equal(firstUseToolFor('subtract'), 'subtract');
  assert.equal(firstUseToolFor('distance'), null);
  assert.equal(firstUseToolFor(null), null);
  assert.equal(firstUseToolFor('toString'), null);
});
