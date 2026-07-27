import test from 'node:test';
import assert from 'node:assert/strict';
import { parseLtNumber } from './parseLtNumber.js';

test('parseLtNumber: comma decimal', () => {
  assert.equal(parseLtNumber('12,5'), 12.5);
  assert.equal(parseLtNumber('0,05'), 0.05);
  assert.equal(parseLtNumber(',5'), 0.5);
});

test('parseLtNumber: space thousands + comma decimal', () => {
  assert.equal(parseLtNumber('1 234,56'), 1234.56);
  assert.equal(parseLtNumber('1 234,56'), 1234.56);   // NBSP
  assert.equal(parseLtNumber('1 234,56'), 1234.56);   // narrow NBSP
});

test('parseLtNumber: dot thousands + comma decimal', () => {
  assert.equal(parseLtNumber('1.234,56'), 1234.56);
  assert.equal(parseLtNumber('1.234.567,89'), 1234567.89);
});

test('parseLtNumber: plain dot decimal still works', () => {
  assert.equal(parseLtNumber('12.5'), 12.5);
  assert.equal(parseLtNumber('12'), 12);
  assert.equal(parseLtNumber('-3,5'), -3.5);
});

test('parseLtNumber: dot-only thousands groups', () => {
  assert.equal(parseLtNumber('1.234.567'), 1234567);
});

test('parseLtNumber: invalid input → NaN', () => {
  assert.ok(Number.isNaN(parseLtNumber('')));
  assert.ok(Number.isNaN(parseLtNumber('   ')));
  assert.ok(Number.isNaN(parseLtNumber('12,5,6')));
  assert.ok(Number.isNaN(parseLtNumber('abc')));
  assert.ok(Number.isNaN(parseLtNumber('12 €')));
  assert.ok(Number.isNaN(parseLtNumber('1e5')));
  assert.ok(Number.isNaN(parseLtNumber(null)));
  assert.ok(Number.isNaN(parseLtNumber(undefined)));
});

test('parseLtNumber: numbers pass through', () => {
  assert.equal(parseLtNumber(12.5), 12.5);
  assert.ok(Number.isNaN(parseLtNumber(NaN)));
  assert.ok(Number.isNaN(parseLtNumber(Infinity)));
});
