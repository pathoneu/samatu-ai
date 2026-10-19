import test from 'node:test';
import assert from 'node:assert/strict';
import {
  VIEW_DEFAULTS, VIEW_SETTINGS_KEY, cleanSlope, readViewSettings, sanitizeViewSettings, viewChanged, viewCss, writeViewSettings,
} from './viewSettings.js';

const memory = () => {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)) };
};

test('defaults change nothing on the screen', () => {
  assert.equal(viewCss(VIEW_DEFAULTS), '');
  assert.equal(viewChanged(VIEW_DEFAULTS), false);
  assert.equal(VIEW_DEFAULTS.pro, false, 'the pro layer starts OFF — the founder decides');
});

test('values out of range or of the wrong type fall back to the default', () => {
  const s = sanitizeViewSettings({ opacity: 5, cleanBg: -1, gray: 'yes', lineWidth: 'x', extra: 1 });
  assert.equal(s.opacity, 1);
  assert.equal(s.cleanBg, 0);
  assert.equal(s.gray, false);
  assert.equal(s.lineWidth, 2);
  assert.equal('extra' in s, false);
  assert.equal(sanitizeViewSettings({ opacity: 0.05 }).opacity, 0.2);
});

test('settings survive a reload of the page; broken storage gives the defaults', () => {
  const st = memory();
  writeViewSettings({ ...VIEW_DEFAULTS, gray: true, opacity: 0.5 }, st);
  assert.deepEqual(readViewSettings(st), { ...VIEW_DEFAULTS, gray: true, opacity: 0.5 });
  st.setItem(VIEW_SETTINGS_KEY, '{not json');
  assert.deepEqual(readViewSettings(st), VIEW_DEFAULTS);
  assert.deepEqual(readViewSettings(null), VIEW_DEFAULTS);
});

test('the drawing settings touch only the render wrapper, never the marks', () => {
  const css = viewCss({ ...VIEW_DEFAULTS, opacity: 0.6, gray: true, cleanBg: 0.2 });
  assert.match(css, /\[data-drawing-render\] \{ opacity: 0\.6; filter: url\(#tv-clean-bg\) grayscale\(1\); \}/);
  assert.equal(css.split('\n').length, 1);
});

test('labels off hide the room names and the measurement values separately', () => {
  assert.match(viewCss({ ...VIEW_DEFAULTS, names: false }), /data-room-label.*data-ov-label="name".*display: none/);
  const dims = viewCss({ ...VIEW_DEFAULTS, dims: false });
  assert.match(dims, /data-ov-label="dim"/);
  assert.doesNotMatch(dims, /data-room-label/);
});

test('outline fill and width apply only with the pro layer on', () => {
  assert.equal(viewCss({ ...VIEW_DEFAULTS, polyOpacity: 0.4, lineWidth: 4 }), '');
  assert.equal(viewChanged({ ...VIEW_DEFAULTS, polyOpacity: 0.4 }), false);
  assert.match(viewCss({ ...VIEW_DEFAULTS, pro: true, polyOpacity: 0.4, lineWidth: 4 }), /fill-opacity: 0\.4; stroke-width: 4px/);
});

test('„Išvalyti foną" turns every grey lighter than 1 − t into white', () => {
  assert.equal(cleanSlope(0), 1);
  assert.equal(cleanSlope(0.2), 1.25);
  assert.equal(cleanSlope(0.9), cleanSlope(0.4));
});
