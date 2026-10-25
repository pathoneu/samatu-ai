import test from 'node:test';
import assert from 'node:assert/strict';
import { scaleLineBody, scaleLineOutcome, toDisplayPoint } from './scaleLine.js';
import { describeScale, provenanceText } from './scaleProvenance.js';

const t = (key, params = {}) => {
  const table = {
    'project.scaleProvenance.withLabel': '{{label}} — {{phrase}}',
    'project.scaleProvenance.phrase.userLineText': 'jūsų nubrėžta linija ant „{{text}}“',
  };
  return (table[key] || key).replace(/\{\{(\w+)\}\}/g, (_, k) => params[k]);
};

test('an unrotated sheet passes the points through', () => {
  const body = scaleLineBody({ page: 2, a: { x: 100, y: 50 }, b: { x: 300, y: 50 }, pageSize: { width: 842, height: 595 }, rotation: 0 });
  assert.deepEqual(body, { page: 2, p1: [100, 50], p2: [300, 50] });
});

test('a sheet rotated 90 degrees: the point moves with the picture and the display is portrait', () => {
  // mediabox 842 x 595, /Rotate 90 → display 595 x 842; (x,y) → (1-y, x) in fractions
  const p = toDisplayPoint({ x: 421, y: 0 }, { width: 842, height: 595 }, 90);
  assert.deepEqual(p, [595, 421]);
});

test('no sheet size, no request', () => {
  assert.equal(scaleLineBody({ page: 1, a: { x: 1, y: 1 }, b: { x: 9, y: 9 }, pageSize: null }), null);
});

test('an ok answer becomes a scale the chip words as the person\'s line', () => {
  const mpp = (0.0254 / 72) * 50;   // 1:50
  const out = scaleLineOutcome({ status: 'ok', page: 3, scale: { m_per_pt: mpp, source: 'user_line', source_text: '4280' } });
  assert.equal(out.ok, true);
  assert.equal(out.page, 3);
  assert.equal(out.pageScale.label, '1:50');
  const desc = describeScale(out.pageScale);
  assert.equal(desc.state, 'nuskaitytas');
  assert.equal(provenanceText(desc, t), '1:50 — jūsų nubrėžta linija ant „4280“');
});

test('a blank answer keeps the backend sentence; a missing one gets a plain default', () => {
  const r = scaleLineOutcome({ status: 'blank', page: 1, reason: 'Po linija neradau matmens teksto.' });
  assert.deepEqual(r, { ok: false, page: 1, reason: 'Po linija neradau matmens teksto.' });
  assert.match(scaleLineOutcome({ status: 'blank', page: 1 }).reason, /nubrėžkite/i);
  assert.equal(scaleLineOutcome({ status: 'ok', page: 1, scale: { m_per_pt: 0 } }).ok, false);
});
