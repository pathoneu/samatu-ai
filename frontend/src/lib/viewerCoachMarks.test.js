import test from 'node:test';
import assert from 'node:assert/strict';
import { COACH_STEPS, COACH_STORAGE_KEY, coachMarksDone, markCoachMarksDone, coachCardPosition } from './viewerCoachMarks.js';

const memStore = () => {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)) };
};

test('three steps in order: Mastelis → Atstumas → Taisyti kontūrą', () => {
  assert.deepEqual(COACH_STEPS.map((s) => s.title), ['Mastelis', 'Atstumas', 'Taisyti kontūrą']);
  for (const s of COACH_STEPS) assert.ok(s.anchor && s.body.length > 40, s.id);
});

test('the snap marks are explained (orange = drawing, green = measurement)', () => {
  const all = COACH_STEPS.map((s) => s.body).join(' ');
  assert.match(all, /oranžinė/);
  assert.match(all, /žalia/);
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
