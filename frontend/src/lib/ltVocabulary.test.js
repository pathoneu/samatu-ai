/**
 * The words a 52-year-old contractor never has to learn.
 *
 * Design „Rimo kelionė" §1: the app must look like his work, not like an AI
 * product. He recognises a drawing, a room, a row, a quantity, a price and an
 * estimate. He does not recognise — and should never be shown — the words this
 * test bans. They are not typos; every one of them was on screen at some point
 * because a developer wrote the UI in the vocabulary of the pipeline behind it.
 *
 * WHAT IS CHECKED: the user-visible VALUES in lt.json, in the namespaces of the
 * app itself. Key NAMES are exempt — `project.interior.prielaidos` is an
 * identifier, and renaming identifiers breaks nothing but costs a diff nobody
 * can review.
 *
 * WHAT IS NOT CHECKED, and why:
 *  - `landing`, `pricing`… no: marketing copy IS checked. Only `admin` (an
 *    internal tool, where „Ekstrakcijos" is the right word for the person
 *    reading it) and `legal` (wording lawyers own) are out of scope, plus
 *    `landing`, whose copy the founder writes and polishes himself.
 *
 * Adding a word here is cheap. Removing one needs a reason written down.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const lt = JSON.parse(readFileSync(join(HERE, '../i18n/lt.json'), 'utf8'));

// The app's own screens. `admin`, `legal` and `landing` are deliberately out —
// see the header.
const APP_NAMESPACES = [
  'nav', 'lang', 'login', 'register', 'cookie', 'layout', 'dashboard',
  'settings', 'project', 'shared', 'workspace', 'newProject', 'upload',
  'billing', 'usageMeter', 'pricing',
];

// [name, pattern, what to say instead]
const BANNED = [
  ['AI', /(?<![A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž])AI(?![A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž])/,
    'perskaityta iš brėžinio'],
  ['analizė', /analiz/i, 'skaitymas / skaičiavimas'],
  ['ekstrakcija', /ekstrakc/i, 'skaitymas iš brėžinio'],
  ['Vision', /vision/i, 'perskaityta iš brėžinio'],
  ['modelis', /\bmodel/i, '— (nieko apie variklį)'],
  ['pasitikėjimas', /pasitikėjim/i, 'verta peržiūrėti'],
  ['konfidencija', /konfidenc/i, 'verta peržiūrėti'],
  ['tikrintinas', /tikrintin/i, 'peržiūrėti'],
  ['zona', /zon(a|os|ą|ų|ai|oje)\b/i, 'kontūras'],
  ['tier', /\btier\b/i, '—'],
  ['koeficientas', /koeficient/i, 'daugiklis'],
  ['recompute', /recompute/i, 'perskaičiuota'],
  ['ledger', /ledger/i, 'kaip suskaičiuota'],
  ['kvitas', /\bkvit/i, '—'],
  ['pasenusi', /pasenus/i, 'senesnė eilutė'],
  ['pozicija', /pozicij/i, 'eilutė'],
];

/** Every [dotted key, string value] pair under the app's own namespaces. */
function appStrings() {
  const out = [];
  const walk = (node, path) => {
    if (typeof node === 'string') { out.push([path, node]); return; }
    if (node && typeof node === 'object') {
      for (const [k, v] of Object.entries(node)) walk(v, path ? `${path}.${k}` : k);
    }
  };
  for (const ns of APP_NAMESPACES) if (lt[ns] !== undefined) walk(lt[ns], ns);
  return out;
}

test('lt.json: the app screens carry none of the banned pipeline words', () => {
  const strings = appStrings();
  assert.ok(strings.length > 200,
    `expected the app namespaces to hold most of lt.json, got ${strings.length}`);

  const found = [];
  for (const [key, value] of strings) {
    for (const [name, pattern, instead] of BANNED) {
      if (pattern.test(value)) {
        found.push(`  ${key}\n    „${value.slice(0, 120)}"\n    banned: ${name} → say: ${instead}`);
      }
    }
  }
  assert.deepEqual(found, [],
    `Banned words on app screens (design „Rimo kelionė" §1):\n${found.join('\n')}`);
});

test('lt.json: key NAMES are exempt — only what the user reads is checked', () => {
  // `project.interior.prielaidos` is an identifier and must not fail the guard;
  // its VALUE („Nustatymai") is what the contractor sees.
  const key = lt.project?.interior?.prielaidos;
  assert.equal(typeof key, 'string');
  assert.ok(!/prielaid/i.test(key),
    'the Prielaidos button now says Nustatymai; only the key name kept the old word');
});

test('the banned list itself is well formed (a broken regex would pass silently)', () => {
  for (const [name, pattern, instead] of BANNED) {
    assert.equal(typeof name, 'string');
    assert.ok(pattern instanceof RegExp, `${name} needs a RegExp`);
    assert.equal(typeof instead, 'string');
    // Each pattern must actually match the thing it bans, or it protects nothing.
    assert.ok(pattern.test(name) || name === 'AI' || name === 'tier',
      `${name}: the pattern does not match its own name — is it right?`);
  }
});

test('no screen sends him to a „Prielaidos" place — the top-bar button says „Nustatymai"', () => {
  // 2026-10-06: project.interior.windowsNotFoundDesc still said „skiltyje
  // „Prielaidos"" — a panel that has been the „Nustatymai" button for weeks.
  // „prielaida" the NOUN (an assumption) is fine; a quoted place name is not.
  const stale = appStrings().filter(([, v]) => /„Prielaid/.test(v)).map(([k, v]) => `${k}: ${v}`);
  assert.deepEqual(stale, [], `strings that name the old panel:\n${stale.join('\n')}`);
  assert.match(lt.project.interior.windowsNotFoundDesc, /per mygtuką „Nustatymai“/);
  const en = JSON.parse(readFileSync(join(HERE, '../i18n/en.json'), 'utf8'));
  assert.doesNotMatch(en.project.interior.windowsNotFoundDesc, /Assumptions/);
  assert.match(en.project.interior.windowsNotFoundDesc, /“Settings” button/);
});
