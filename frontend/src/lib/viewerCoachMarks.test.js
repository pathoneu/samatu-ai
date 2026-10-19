import test from 'node:test';
import assert from 'node:assert/strict';
import { COACH_STEPS, COACH_STORAGE_KEY, coachMarksDone, markCoachMarksDone, coachCardPosition, modalOpen, MODAL_SELECTOR } from './viewerCoachMarks.js';

const memStore = () => {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)) };
};

test('three steps in order: Mastelis → Atstumas → Taisyti kontūrą', () => {
  assert.deepEqual(COACH_STEPS.map((s) => s.title), ['Mastelis', 'Atstumas', 'Taisyti kontūrą']);
  for (const s of COACH_STEPS) assert.ok(s.anchor && s.body.length > 40, s.id);
});

test('the snap marks are explained by shape (v3: one snap colour, the shape says what the click lands on)', () => {
  const all = COACH_STEPS.map((s) => s.body).join(' ');
  assert.match(all, /kvadratas/);
  assert.match(all, /rombas/);
  assert.match(all, /apskritimas/);
  assert.doesNotMatch(all, /oranžinė|žalia/);
});

test('the steps name the keys of the click model: K, E, Space', () => {
  const byId = Object.fromEntries(COACH_STEPS.map((s) => [s.id, s.body]));
  assert.match(byId.calibrate, /\(K\)/);
  assert.match(byId.outline, /\(E\)/);
  assert.match(byId.distance, /tarpas — tempti brėžinį/);
  assert.match(byId.distance, /antru spustelėjimu/);
});

test('shown once: done after markCoachMarksDone, under the agreed key', () => {
  const s = memStore();
  assert.equal(coachMarksDone(s), false);
  markCoachMarksDone(s);
  assert.equal(s.getItem(COACH_STORAGE_KEY), '1');
  assert.equal(COACH_STORAGE_KEY, 'samatu_viewer_onboarded');
  assert.equal(coachMarksDone(s), true);
});

test('broken storage never nags', () => {
  const broken = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } };
  assert.equal(coachMarksDone(broken), true);
  assert.doesNotThrow(() => markCoachMarksDone(broken));
});

test('card sits under its anchor and stays inside the viewport', () => {
  const p = coachCardPosition({ left: 600, width: 80, bottom: 40 }, { vw: 1280, vh: 800 });
  assert.equal(p.top, 50);
  assert.equal(p.left, 640 - 160);
  assert.equal(p.arrowLeft, 160);
  const edge = coachCardPosition({ left: 1250, width: 20, bottom: 40 }, { vw: 1280, vh: 800 });
  assert.ok(edge.left + 320 <= 1280 - 12 + 0.001);
  const none = coachCardPosition(null, { vw: 1280, vh: 800 });
  assert.equal(none.arrowLeft, null);
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
