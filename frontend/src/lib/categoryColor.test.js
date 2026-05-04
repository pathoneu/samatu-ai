// frontend/src/lib/categoryColor.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { categoryAccent, BRAND_PRIMARY } from './categoryColor.js';

test('categoryAccent: known categories return brand primary blue', () => {
  assert.equal(categoryAccent('apdaila'), BRAND_PRIMARY);
  assert.equal(categoryAccent('plyteliu_darbai'), BRAND_PRIMARY);
  assert.equal(categoryAccent('elektra'), BRAND_PRIMARY);
});

test('categoryAccent: unknown skyrius defaults to brand primary', () => {
  assert.equal(categoryAccent('something_new'), BRAND_PRIMARY);
  assert.equal(categoryAccent(null), BRAND_PRIMARY);
  assert.equal(categoryAccent(undefined), BRAND_PRIMARY);
});

test('BRAND_PRIMARY is the construction blue from index.css', () => {
  assert.equal(BRAND_PRIMARY, '#2a6fb5');
});
