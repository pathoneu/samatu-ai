import test from 'node:test';
import assert from 'node:assert/strict';
import { CURSOR_HINT_MODES, CURSOR_HINT_EVENT, cursorHintFor, flashCursorHint } from './cursorHints.js';
import { RAIL_TOOLS } from './toolRail.js';

test('every mode has a sentence; rest has none', () => {
  for (const mode of CURSOR_HINT_MODES) {
    const text = cursorHintFor({ mode, fill: { nr: '04' }, countType: { label: 'Rozetės', n: 0 } });
    assert.equal(typeof text, 'string', mode);
    assert.ok(text.length > 5 && text.length <= 90, `${mode}: „${text}" should be one short line`);
  }
  assert.equal(cursorHintFor({}), null);
  assert.equal(cursorHintFor({ mode: null }), null);
});

test('every tool on the rail is a hint mode', () => {
  for (const t of RAIL_TOOLS.filter((x) => !x.toggle)) assert.ok(CURSOR_HINT_MODES.includes(t.id), t.id);
});

test('the sentence follows the state: the next point, then how to finish', () => {
  assert.equal(cursorHintFor({ mode: 'distance', points: 0 }), 'Spustelėkite pradžią');
  assert.match(cursorHintFor({ mode: 'distance', points: 1 }), /^Spustelėkite pabaigą — atstumas įsirašys/);
  assert.match(cursorHintFor({ mode: 'distance', points: 2 }), /su Shift — tęsti/);
  assert.match(cursorHintFor({ mode: 'distance', points: 1, shift: true }), /tęsiamas/);
  assert.equal(cursorHintFor({ mode: 'area', points: 0 }), 'Spustelėkite pirmą kampą');
  assert.equal(cursorHintFor({ mode: 'area', points: 2 }), 'Spustelėkite kitą kampą · Shift — tik tiesiai arba 45°');
  assert.match(cursorHintFor({ mode: 'area', points: 3 }), /dukart arba Enter — baigti/);
  assert.match(cursorHintFor({ mode: 'perimeter', points: 2 }), /baigti/);
  assert.equal(cursorHintFor({ mode: 'calibrate' }), 'Spustelėkite žinomo ilgio pradžią');
  assert.equal(cursorHintFor({ mode: 'calibrate', calibPoint: true }), 'Spustelėkite žinomo ilgio pabaigą');
});

test('count names the type and its tally, or says what is missing', () => {
  assert.match(cursorHintFor({ mode: 'count' }), /tipą/);
  assert.match(cursorHintFor({ mode: 'count', countType: { label: 'Rozetės', n: 3 } }), /^Rozetės: .*pažymėta 3/);
});

test('room tools, find similar and fill read their own state', () => {
  assert.equal(cursorHintFor({ mode: 'room' }), 'Spustelėkite patalpos viduje');
  assert.match(cursorHintFor({ mode: 'room', roomPhase: 'reading' }), /Skaitomas/);
  assert.match(cursorHintFor({ mode: 'room', roomPhase: 'proposed' }), /išsaugoti/);
  assert.equal(cursorHintFor({ mode: 'fill', fill: { nr: '04', busy: false } }), 'Spustelėkite patalpos 04 viduje');
  assert.match(cursorHintFor({ mode: 'fill', fill: { nr: '04', busy: true } }), /Ieškoma/);
  assert.match(cursorHintFor({ mode: 'split', outlineTool: {} }), /prasideda/);
  assert.match(cursorHintFor({ mode: 'split', outlineTool: { a: [0, 0] } }), /baigiasi/);
  assert.match(cursorHintFor({ mode: 'split', outlineTool: { a: [0, 0], b: [1, 1] } }), /lieka/);
  assert.match(cursorHintFor({ mode: 'merge', outlineTool: {} }), /gretimą/);
  assert.match(cursorHintFor({ mode: 'subtract', outlineTool: { shape: 'rect' } }), /stačiakampį/);
  assert.match(cursorHintFor({ mode: 'findSimilar', symbolPhase: 'searching' }), /Ieškoma/);
});

test('a layer can flash why its click did nothing', () => {
  const target = new EventTarget();
  let got = null;
  target.addEventListener(CURSOR_HINT_EVENT, (e) => { got = e.detail.text; });
  flashCursorHint('Nieko nepasikeitė: spustelėkite patalpos viduje', target);
  assert.equal(got, 'Nieko nepasikeitė: spustelėkite patalpos viduje');
  flashCursorHint('', target);
  assert.equal(got, 'Nieko nepasikeitė: spustelėkite patalpos viduje');
});

test('W5-A follow-up: once a draft has its first point, the hint says what Shift does — never only in a tooltip', () => {
  for (const mode of ['distance', 'area', 'perimeter']) {
    assert.doesNotMatch(cursorHintFor({ mode, points: 0 }), /45°/, mode);
    for (const points of [1, 2, 3, 5]) assert.match(cursorHintFor({ mode, points }), /Shift — .*tik tiesiai arba 45°/, `${mode} ${points}`);
  }
});
