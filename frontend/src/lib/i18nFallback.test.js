import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import i18next from 'i18next';
import { lookupLithuanian, makeMissingKeyHandler, interpolate } from './i18nFallback.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const lt = JSON.parse(readFileSync(join(HERE, '../i18n/lt.json'), 'utf8'));

test('direct lookup: plain, plural with count, variables', () => {
  assert.equal(lookupLithuanian(lt, 'project.assumptions.puttyLevel'), 'Glaistymo lygis');
  assert.equal(lookupLithuanian(lt, 'project.sanity.pillWarnings', { count: 1 }), '1 įspėjimas');
  assert.equal(lookupLithuanian(lt, 'project.sanity.pillWarnings', { count: 3 }), '3 įspėjimai');
  assert.equal(lookupLithuanian(lt, 'project.sanity.pillWarnings', { count: 11 }), '11 įspėjimų');
  assert.equal(lookupLithuanian(lt, 'no.such.key'), undefined);
  assert.equal(interpolate('{{a}} ir {{ b }}', { a: 1, b: 'du' }), '1 ir du');
});

test('a store that lost Lithuanian still renders Lithuanian, never the key', async () => {
  // The failure the founder saw: i18next resolves nothing. Here the instance has an EMPTY catalogue.
  const i18n = i18next.createInstance();
  await i18n.init({
    lng: 'lt', fallbackLng: 'lt', resources: { lt: { translation: {} } },
    interpolation: { escapeValue: false },
    parseMissingKeyHandler: makeMissingKeyHandler(lt, { warn: () => {} }),
  });
  assert.equal(i18n.t('project.mainView.beVat'), 'Be PVM');
  assert.equal(i18n.t('project.sanity.pillWarnings', { count: 2 }), '2 įspėjimai');
  assert.equal(i18n.t('project.provenance.eksplikacijaLabel'), 'iš eksplikacijos');
});

test('unknown key: the default text, else empty — and one warning per key', async () => {
  const warned = [];
  const i18n = i18next.createInstance();
  await i18n.init({
    lng: 'en', fallbackLng: 'lt', resources: { en: { translation: {} }, lt: { translation: lt } },
    interpolation: { escapeValue: false },
    parseMissingKeyHandler: makeMissingKeyHandler(lt, { warn: (m) => warned.push(m) }),
  });
  assert.equal(i18n.t('zz.unknown.key', 'Numatytasis tekstas'), 'Numatytasis tekstas');
  assert.equal(i18n.t('zz.other.key'), '');
  assert.equal(i18n.t('zz.other.key'), '');
  assert.equal(warned.filter((m) => m.includes('zz.other.key')).length, 1);
  // a key English lacks falls back to Lithuanian through i18next itself
  assert.equal(i18n.t('project.assumptions.puttyLevel'), 'Glaistymo lygis');
});
