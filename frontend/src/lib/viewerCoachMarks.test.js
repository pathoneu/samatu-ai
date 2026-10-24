import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  COACH_STEPS, COACH_STORAGE_KEY, COACH_STEP_KEY, COACH_MAX_WORDS, coachMarksDone, markCoachMarksDone, coachCardPosition,
  coachStartStep, saveCoachStep, resetCoachMarks, wordCount, modalOpen, MODAL_SELECTOR, coachAvoid,
} from './viewerCoachMarks.js';
import { shortcutById } from './viewerShortcuts.js';
import { isBannedText } from './userText.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const lt = JSON.parse(readFileSync(join(HERE, '../i18n/lt.json'), 'utf8'));
const en = JSON.parse(readFileSync(join(HERE, '../i18n/en.json'), 'utf8'));

const memStore = () => {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k) };
};

test('ten cards in the order a person meets the screen', () => {
  assert.deepEqual(COACH_STEPS.map((s) => s.id), [
    'sheets', 'tools', 'roomClick', 'roomTool', 'scale', 'measure', 'legend', 'patikra', 'samata', 'siusti',
  ]);
  for (const s of COACH_STEPS) assert.ok(s.anchor, s.id);
});

test('each card: a title and ONE sentence of at most 12 words, in lt and en, no pipeline words', () => {
  for (const [lang, dict] of [['lt', lt], ['en', en]]) {
    for (const s of COACH_STEPS) {
      const c = dict.project.coach[s.id];
      assert.ok(c?.title && c?.body, `${lang} ${s.id}`);
      assert.ok(wordCount(c.body) <= COACH_MAX_WORDS, `${lang} ${s.id}: ${wordCount(c.body)} words — ${c.body}`);
      // one sentence: a single full stop, at the end
      assert.equal((c.body.match(/[.!?](\s|$)/g) || []).length, 1, `${lang} ${s.id}: ${c.body}`);
      if (lang === 'lt') {
        assert.equal(isBannedText(c.title), false, c.title);
        assert.equal(isBannedText(c.body), false, c.body);
      }
    }
  }
});

test('at most one key per card, and the named shortcuts exist (R, K, 2, G, ?)', () => {
  const keyed = COACH_STEPS.filter((s) => s.key);
  for (const s of keyed) {
    assert.equal(typeof s.key, 'string');
    if (s.key !== 'Enter') assert.ok(shortcutById(s.key), `${s.id} → ${s.key}`);
  }
  const byId = Object.fromEntries(COACH_STEPS.map((s) => [s.id, s.key]));
  assert.equal(byId.roomTool, 'toolRoom');
  assert.equal(byId.legend, 'toolLegend');
  assert.equal(byId.scale, 'toolCalibrate');
});

test('shown once: done after markCoachMarksDone, under the agreed key', () => {
  const s = memStore();
  assert.equal(coachMarksDone(s), false);
  markCoachMarksDone(s);
  assert.equal(s.getItem(COACH_STORAGE_KEY), '1');
  assert.equal(COACH_STORAGE_KEY, 'samatu_viewer_onboarded');
  assert.equal(coachMarksDone(s), true);
});

test('resumable: the card he reached comes back; done or reset forgets it', () => {
  const s = memStore();
  assert.equal(coachStartStep(s), 0);
  saveCoachStep(4, s);
  assert.equal(s.getItem(COACH_STEP_KEY), '4');
  assert.equal(coachStartStep(s), 4);
  saveCoachStep(99, s);
  assert.equal(coachStartStep(s), COACH_STEPS.length - 1, 'clamped');
  markCoachMarksDone(s);
  assert.equal(s.getItem(COACH_STEP_KEY), null);
  saveCoachStep(3, s);
  resetCoachMarks(s);
  assert.equal(coachMarksDone(s), false);
  assert.equal(coachStartStep(s), 0);
});

test('broken storage never nags', () => {
  const broken = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); }, removeItem() { throw new Error('denied'); } };
  assert.equal(coachMarksDone(broken), true);
  assert.doesNotThrow(() => markCoachMarksDone(broken));
  assert.equal(coachStartStep(broken), 0);
  assert.doesNotThrow(() => saveCoachStep(2, broken));
});

test('card sits under its anchor and stays inside the viewport', () => {
  const p = coachCardPosition({ left: 600, top: 20, width: 80, height: 20, bottom: 40 }, { vw: 1280, vh: 800 });
  assert.equal(p.top, 50);
  assert.equal(p.left, 640 - 160);
  assert.equal(p.arrowLeft, 160);
  const edge = coachCardPosition({ left: 1250, top: 20, width: 20, height: 20, bottom: 40 }, { vw: 1280, vh: 800 });
  assert.ok(edge.left + 320 <= 1280 - 12 + 0.001);
  const none = coachCardPosition(null, { vw: 1280, vh: 800 });
  assert.equal(none.arrowLeft, null);
});

test('above: over the anchor with the arrow pointing down (the scale chip sits at the bottom)', () => {
  const p = coachCardPosition({ left: 200, top: 760, width: 160, height: 28, bottom: 788 }, { vw: 1440, vh: 900, cardH: 140, side: 'above' });
  assert.equal(p.top, 760 - 10 - 140);
  assert.equal(p.arrowDown, true);
  assert.ok(p.arrowLeft > 0);
});

test('over: inside the drawing\'s top edge, centred, no arrow', () => {
  const p = coachCardPosition({ left: 200, top: 100, width: 800, height: 700, bottom: 800 }, { vw: 1440, vh: 900, cardW: 300, side: 'over' });
  assert.equal(p.top, 124);
  assert.equal(p.left, 200 + 250);
  assert.equal(p.arrowLeft, null);
  assert.equal(p.arrowTop, null);
});

test('the walkthrough steps aside while a dialog or overlay is open (v3 M6)', () => {
  const docWith = (hit) => ({ querySelector: (sel) => { assert.equal(sel, MODAL_SELECTOR); return hit; } });
  assert.equal(modalOpen(docWith({})), true);
  assert.equal(modalOpen(docWith(null)), false);
  assert.equal(modalOpen({ querySelector: () => { throw new Error('bad selector'); } }), false);
  assert.equal(modalOpen(null), false);
  for (const part of ['[role="dialog"][data-state="open"]', '[role="alertdialog"]', '.fixed.inset-0.z-50']) {
    assert.ok(MODAL_SELECTOR.includes(part), part);
  }
});

test('beside a tool card (side right) the card stands right of it, arrow at its middle', () => {
  const p = coachCardPosition({ left: 120, top: 300, width: 64, height: 34, bottom: 334 }, { vw: 1280, vh: 720, side: 'right' });
  assert.equal(p.left, 120 + 64 + 10);
  assert.equal(p.top, 288);
  assert.equal(p.arrowLeft, null);
  assert.equal(p.arrowTop, 300 + 17 - 288);
  const low = coachCardPosition({ left: 120, top: 690, width: 64, height: 20, bottom: 710 }, { vw: 1280, vh: 720, side: 'right' });
  assert.ok(low.top + 220 <= 720 - 12 + 0.001, 'kept inside the window');
});

test('a card never covers the room header: moved under it when anchored, else it waits', () => {
  // the room sheet at 1440×900: the header strip spans the right half; the anchor-less card sat centred near the top
  const header = { left: 637, top: 137, width: 787, height: 116 };
  const pos = coachCardPosition(null, { vw: 1440, vh: 900, cardW: 300, cardH: 120 });
  assert.equal(coachAvoid(pos, { cardW: 300, cardH: 120, vh: 900, avoid: [header], anchored: false }), null);
  const moved = coachAvoid({ left: 700, top: 120, arrowLeft: 40, arrowTop: null, arrowDown: false }, { cardW: 300, cardH: 120, vh: 900, avoid: [header] });
  assert.equal(moved.top, 137 + 116 + 10);
  assert.equal(moved.arrowLeft, null);
  // no room under it → waits
  assert.equal(coachAvoid({ left: 700, top: 120 }, { cardW: 300, cardH: 700, vh: 900, avoid: [header] }), null);
  // clear of it, or nothing to avoid → unchanged
  const clear = { left: 120, top: 100, arrowLeft: null, arrowTop: 30, arrowDown: false };
  assert.equal(coachAvoid(clear, { cardW: 300, cardH: 120, vh: 900, avoid: [header] }), clear);
  assert.equal(coachAvoid(clear, { cardW: 300, cardH: 120, vh: 900 }), clear);
  assert.equal(coachAvoid(clear, { cardW: 300, cardH: 120, vh: 900, avoid: [{ left: 0, top: 0, width: 0, height: 0 }] }), clear);
});

test('wordCount ignores dashes and punctuation', () => {
  assert.equal(wordCount('Spustelėkite lapą — jis atsidarys brėžinyje.'), 5);
  assert.equal(wordCount(''), 0);
});
