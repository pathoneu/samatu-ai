/**
 * lib/roomKampai — the room grid shows the backend's per-room corner length
 * or nothing; never a second formula of its own (2026-10-03 review).
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  backendKampaiM, kampaiInputsChanged, withoutBackendKampai, kampaiTotalM,
} from './roomKampai.js';

test('the backend value is read from kampai_m, then the kampu_metrai alias', () => {
  assert.equal(backendKampaiM({ kampai_m: 48.1, kampu_metrai: 48.1 }), 48.1);
  assert.equal(backendKampaiM({ kampu_metrai: 30.5 }), 30.5);
  assert.equal(backendKampaiM({ kampai_m: '12.4' }), 12.4);
  // A room whose walls are not painted: the backend says 0 — that is a value.
  assert.equal(backendKampaiM({ kampai_m: 0 }), 0);
});

test('a legacy room with no backend value shows nothing — never perim + 4 × H', () => {
  const legacy = { nr: '01', perimetras_m: 14, lubu_aukstis_m: 2.7, paskirtis: 'gyvenamoji' };
  assert.equal(backendKampaiM(legacy), null);
  assert.notEqual(backendKampaiM(legacy), 14 + 4 * 2.7);
  assert.equal(backendKampaiM({ kampai_m: null }), null);
  assert.equal(backendKampaiM({ kampai_m: '' }), null);
  assert.equal(backendKampaiM({ kampai_m: NaN }), null);
  assert.equal(backendKampaiM(null), null);
});

test('an edit to what the corners came from makes the backend value stale', () => {
  const room = { perimetras_m: 14, lubu_aukstis_m: 2.7, paskirtis: 'gyvenamoji', plotas_m2: 12, kampai_m: 40 };
  assert.equal(kampaiInputsChanged(room, { ...room, pavadinimas: 'Svetainė' }), false);
  assert.equal(kampaiInputsChanged(room, { ...room, perimetras_m: '14' }), false, 'same number, other type');
  assert.equal(kampaiInputsChanged(room, { ...room, perimetras_m: 15 }), true);
  assert.equal(kampaiInputsChanged(room, { ...room, lubu_aukstis_m: 3.1 }), true);
  assert.equal(kampaiInputsChanged(room, { ...room, paskirtis: 'vonia' }), true);
  assert.equal(kampaiInputsChanged(room, { ...room, plotas_m2: 13 }), true);
});

test('dropping the stale value removes both names and keeps the rest', () => {
  const out = withoutBackendKampai({ nr: '1', kampai_m: 40, kampu_metrai: 40, plotas_m2: 12 });
  assert.deepEqual(out, { nr: '1', plotas_m2: 12 });
  assert.equal(backendKampaiM(out), null);
});

test('the total is shown only when every room carries the backend value', () => {
  assert.equal(kampaiTotalM([{ kampai_m: 40 }, { kampu_metrai: 2.5 }, { kampai_m: 0 }]), 42.5);
  assert.equal(kampaiTotalM([{ kampai_m: 40 }, { nr: 'legacy' }]), null, 'a partial sum is not a total');
  assert.equal(kampaiTotalM([]), null);
  assert.equal(kampaiTotalM(undefined), null);
});
