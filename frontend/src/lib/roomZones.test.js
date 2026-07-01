import test from 'node:test';
import assert from 'node:assert/strict';
import {
  roomZoneColor, confidenceHex, ROOM_ZONE_COLORS, CONFIDENCE_HEX,
} from './roomZones.js';

test('roomZoneColor: known paskirtis → its hue', () => {
  assert.equal(roomZoneColor('miegamoji'), '#3b82f6');
  assert.equal(roomZoneColor('vonia'), '#06b6d4');
  assert.equal(roomZoneColor('virtuve'), '#f59e0b');
});

test('roomZoneColor: unknown / missing paskirtis → default green', () => {
  assert.equal(roomZoneColor('nesamone'), '#10b981');
  assert.equal(roomZoneColor(undefined), '#10b981');
});

test('confidenceHex: maps the four confidence levels', () => {
  assert.equal(confidenceHex('high'), '#16a34a');
  assert.equal(confidenceHex('medium'), '#d97706');
  assert.equal(confidenceHex('low'), '#dc2626');
  assert.equal(confidenceHex('unknown'), '#9ca3af');
});

test('confidenceHex: unrecognised value → unknown grey', () => {
  assert.equal(confidenceHex('bogus'), '#9ca3af');
  assert.equal(confidenceHex(undefined), '#9ca3af');
});

test('color maps are frozen-ish plain objects', () => {
  assert.equal(typeof ROOM_ZONE_COLORS, 'object');
  assert.equal(CONFIDENCE_HEX.high, '#16a34a');
});
