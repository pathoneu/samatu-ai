import test from 'node:test';
import assert from 'node:assert/strict';
import {
  boxFromDrag, normalizeCandidates, visibleCandidates, formatScore, countLabel, groupByPage,
  unusualPages, countsByPage, planAllPages, pageRanges, candidatesToMeasurements, klassFor,
  decisionsToRecord, aiMarkCount, AI_CONFIDENCE, SYMBOL_SOURCE, DEFAULT_THRESHOLD, MIN_THRESHOLD,
} from './symbolSearch.js';
import { normalizeConfidence, CONF_GELTONA } from './confidence.js';

const raw = [
  { x: 10, y: 10, box_pt: [5, 5, 15, 15], score: 1, is_source: true },
  { x: 50, y: 10, box_pt: [45, 5, 55, 15], score: 0.91 },
  { x: 90, y: 10, box_pt: [85, 5, 95, 15], score: 0.86 },
  { x: 130, y: 10, box_pt: [125, 5, 135, 15], score: 0.8 },
];

test('boxFromDrag orders the corners and refuses a click-sized box', () => {
  assert.deepEqual(boxFromDrag({ x: 30, y: 40 }, { x: 10, y: 12 }), [10, 12, 30, 40]);
  assert.equal(boxFromDrag({ x: 10, y: 10 }, { x: 12, y: 30 }), null);
  assert.equal(boxFromDrag(null, { x: 1, y: 1 }), null);
});

test('normalizeCandidates gives stable per-page ids and keeps the source flag', () => {
  const c = normalizeCandidates(3, raw);
  assert.equal(c[0].id, '3:0');
  assert.equal(c[0].page, 3);
  assert.equal(c[0].isSource, true);
  assert.deepEqual(c[1].box, [45, 5, 55, 15]);
});

test('the slider filters by score and removed ones never come back', () => {
  const c = normalizeCandidates(1, raw);
  assert.equal(visibleCandidates(c, 0.85).length, 3);
  assert.equal(visibleCandidates(c, 0.9).length, 2);
  const v = visibleCandidates(c, 0.75, new Set(['1:1']));
  assert.deepEqual(v.map((x) => x.id), ['1:0', '1:2', '1:3']);
});

test('defaults: the slider starts above the measured noise and the floor below it', () => {
  // measured on objektas_h p1: wrong hits up to 0.856, real ones from 0.874
  assert.ok(DEFAULT_THRESHOLD > 0.856 && DEFAULT_THRESHOLD <= 0.874);
  assert.ok(MIN_THRESHOLD < DEFAULT_THRESHOLD);
});

test('count label speaks Lithuanian with a decimal comma', () => {
  assert.equal(formatScore(0.72), '0,72');
  assert.equal(countLabel({ found: 14, shown: 9, threshold: 0.72 }), 'rasta 14, rodoma 9 nuo 0,72');
});

test('groupByPage keeps sheets in order', () => {
  const items = [...normalizeCandidates(4, raw.slice(0, 1)), ...normalizeCandidates(1, raw.slice(0, 2))];
  assert.deepEqual(groupByPage(items).map((g) => [g.page, g.items.length]), [[1, 2], [4, 1]]);
});

test('unusual: more than 60 on a sheet is always flagged', () => {
  assert.deepEqual(unusualPages({ 1: 61 }), { 1: 'many' });
  assert.deepEqual(unusualPages({ 1: 60 }), {});
});

test('unusual: 3x the median of sheets with hits, only with three such sheets', () => {
  assert.deepEqual(unusualPages({ 1: 4, 2: 5, 3: 4, 4: 20 }), { 4: 'ratio' });
  assert.deepEqual(unusualPages({ 1: 4, 2: 20 }), {});          // two sheets: no "usual" to compare with
  assert.deepEqual(unusualPages({ 1: 4, 2: 0, 3: 0, 4: 0, 5: 5, 6: 4 }), {});  // empty sheets do not drag the median to 0
  assert.deepEqual(unusualPages({ 1: 4, 2: 5, 3: 4, 4: 12 }), {}); // exactly 3x is not more than 3x
});

test('countsByPage', () => {
  const items = [...normalizeCandidates(1, raw), ...normalizeCandidates(2, raw.slice(0, 1))];
  assert.deepEqual(countsByPage(items), { 1: 4, 2: 1 });
});

test('planAllPages: template sheet first, cap, the rest named as skipped', () => {
  assert.deepEqual(planAllPages(5, 3, { maxPages: 3 }), { pages: [3, 1, 2], skipped: [4, 5] });
  assert.deepEqual(planAllPages(3, 1, { alreadyDone: [1] }), { pages: [2, 3], skipped: [] });
});

test('pageRanges', () => {
  assert.equal(pageRanges([13, 14, 15, 16, 2, 7, 8]), '2, 7–8, 13–16');
  assert.equal(pageRanges([]), '');
});

test('kept candidates become count marks flagged as AI-found, yellow', () => {
  const type = { id: 'durys-ai', label: 'Durys (AI)', color: '#16a34a' };
  const ms = candidatesToMeasurements(normalizeCandidates(1, raw.slice(1, 3)), type);
  assert.equal(ms.length, 2);
  for (const m of ms) {
    assert.equal(m.kind, 'count');
    assert.equal(m.page, 1);
    assert.equal(m.typeId, 'durys-ai');
    assert.equal(m.color, '#16a34a');
    assert.equal(m.confidence, AI_CONFIDENCE);
    assert.equal(m.source, SYMBOL_SOURCE);
    assert.equal(m.points.length, 1);
    assert.ok(m.id);
  }
  assert.deepEqual(ms[0].points[0], { x: 50, y: 10 });
  // The list's confidence vocabulary reads it as „Patikrinti", never as green.
  assert.equal(normalizeConfidence(AI_CONFIDENCE), CONF_GELTONA);
});

test('klassFor fits the backend class pattern', () => {
  assert.equal(klassFor({ id: 'durys-ai' }), 'durys-ai');
  assert.equal(klassFor({ id: '' }), 'simbolis');
  assert.match(klassFor({ id: 'x'.repeat(80) }), /^[a-z0-9_-]{1,40}$/);
});

test('decisions: kept = accept, removed by hand = reject, hidden by the slider = not sent', () => {
  const c = normalizeCandidates(1, raw);
  const d = decisionsToRecord(c, 0.85, new Set(['1:2']));
  assert.deepEqual(d.map((x) => [x.c.id, x.decision]), [['1:0', 'accept'], ['1:1', 'accept'], ['1:2', 'reject']]);
});

test('aiMarkCount counts only AI-found marks of the type', () => {
  const ms = [
    { kind: 'count', typeId: 'a', source: SYMBOL_SOURCE },
    { kind: 'count', typeId: 'a', source: 'user' },
    { kind: 'count', typeId: 'b', source: SYMBOL_SOURCE },
  ];
  assert.equal(aiMarkCount(ms, 'a'), 1);
});
