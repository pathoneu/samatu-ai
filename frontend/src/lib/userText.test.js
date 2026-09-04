import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cleanUserText, isBannedText, _resetConfidentialCache, FALLBACK_TEXT } from './userText.js';

const OLD = 'Formulė kalibruota pagal 1 rangovo samatą (Kliento) — apima ginčytiną pusinių kampų dedamąją; tikslumas nepatvirtintas (reikia daugiau etalonų); Gretimybės analizė nerado pertvarų (žinomai per maža)';

test('current guidance passes through untouched', () => {
  const ok = 'Kampų ilgis apskaičiuotas iš patalpų geometrijos (išoriniai kampai × aukštis) — suskaičiuokite dažomus kampus plane ir palyginkite.';
  assert.equal(cleanUserText(ok), ok);
  assert.equal(isBannedText(ok), false);
});

test('an old confession is removed entirely, never printed', () => {
  const out = cleanUserText(OLD);
  assert.equal(isBannedText(out), false);
  assert.equal(out, FALLBACK_TEXT);
});

test('a clean clause survives next to a banned one', () => {
  assert.equal(cleanUserText('Palyginkite su durų specifikacija. Kalibruota pagal etaloną (2 projektai).'),
    'Palyginkite su durų specifikacija.');
});

test('customer terms come from the environment', () => {
  process.env.VITE_CONFIDENTIAL_TERMS = 'Slaptas klientas, Kita gatvė 7';
  _resetConfidentialCache();
  assert.equal(isBannedText('pagal Slaptas Klientas projektą'), true);
  assert.equal(cleanUserText('Pagal Slaptas klientas projektą. Patikrinkite.'), 'Patikrinkite.');
  delete process.env.VITE_CONFIDENTIAL_TERMS;
  _resetConfidentialCache();
  assert.equal(isBannedText('pagal Slaptas Klientas projektą'), false);
});

test('non-strings and empties are returned as-is', () => {
  assert.equal(cleanUserText(null), null);
  assert.equal(cleanUserText(''), '');
  assert.equal(cleanUserText(undefined), undefined);
});
