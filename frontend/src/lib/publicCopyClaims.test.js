/**
 * Public copy must not promise what the product does not do (audit 2026-09-29, G5).
 *
 * Facts this guards (as of 2026-09-29):
 *  - the product does interior finishing quantities only; facades, roofs,
 *    earthworks and concrete are hidden and must not be sold;
 *  - a run takes roughly 15–35 min, not "a few minutes";
 *  - checking = a handful of questions with the place on the drawing beside
 *    each number, not "check only the flagged rows";
 *  - scanned PDFs work with less (areas from the room table, walls estimated);
 *  - no accuracy percentage is promised;
 *  - the Studio tier has no priority processing and no shared price lists.
 *
 * The founder rewords this copy freely; this test only bans the specific
 * claims that were false, not any particular new wording.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = join(HERE, '..');
const read = (p) => readFileSync(p, 'utf8');

// Marketing / pricing / brand-panel namespaces plus the in-app timing strings.
const JSON_SCOPES = [
  'landing', 'pricing', 'login', 'register',
  'dashboard.empty', 'project.reextract',
];

function scopedStrings(lang) {
  const root = JSON.parse(read(join(SRC, `i18n/${lang}.json`)));
  const out = [];
  const walk = (node, path) => {
    if (path.includes('.oauthErr')) return; // Google sign-in errors, not a product claim
    if (typeof node === 'string') { out.push([`${lang}.json ${path}`, node]); return; }
    if (node && typeof node === 'object') {
      for (const [k, v] of Object.entries(node)) walk(v, `${path}.${k}`);
    }
  };
  for (const scope of JSON_SCOPES) {
    const node = scope.split('.').reduce((n, k) => (n ? n[k] : undefined), root);
    if (node !== undefined) walk(node, scope);
  }
  return out;
}

function pageTexts() {
  const bofu = join(SRC, 'pages/bofu');
  const files = [
    join(SRC, 'pages/Duk.jsx'),
    ...readdirSync(bofu).filter((f) => f.endsWith('.jsx')).map((f) => join(bofu, f)),
    join(SRC, '../index.html'),
    join(SRC, '../public/llms.txt'),
  ];
  return files.map((f) => [relative(join(SRC, '..'), f), read(f)]);
}

// [name, pattern] — each one a claim that was on the public pages and is false.
const FALSE_CLAIMS = [
  ['"a few minutes"', /kelias minutes|few minutes/i],
  ['bare "in minutes"', /per minutes\b|in minutes\b|in minutes;/i],
  ['old run time', /3[–-]8 min|iki 8 min|up to 8 min|10–15 minučių/i],
  ['accuracy percentage', /~\s?1\s?%/],
  ['"check only the flagged rows"', /Tikrinate tik tai|check only what|Likusios 43|remaining 43 lines were read/i],
  ['scanned = vector', /vektoriniai ar skenuoti|tiek skenuoti|vector or scanned/i],
  ['Studio extras that do not exist', /prioritetinis apdorojimas|priority processing|bendri kainynai|shared price lists/i],
  ['"all types"', /visų tipų|all types|all quantity types/i],
];

// Hidden construction types — banned only where the product is being sold
// (the renovation guide may still explain facade norms as background).
const HIDDEN_TYPES = /fasad|stog|(^|[^a-ząčęėįšųūž])iškas|facade|roofing|excavation/i;

test('public copy carries none of the false product claims', () => {
  const found = [];
  for (const [where, text] of [...scopedStrings('lt'), ...scopedStrings('en'), ...pageTexts()]) {
    for (const [name, pattern] of FALSE_CLAIMS) {
      if (pattern.test(text)) found.push(`${where}: ${name} — „${text.match(pattern)[0]}"`);
    }
  }
  assert.deepEqual(found, [], `False claims still in public copy:\n${found.join('\n')}`);
});

test('landing, pricing and sign-in copy sell no hidden construction types', () => {
  const found = [];
  for (const lang of ['lt', 'en']) {
    for (const [where, text] of scopedStrings(lang)) {
      if (where.includes('project.reextract')) continue;
      if (HIDDEN_TYPES.test(text)) found.push(`${where}: „${text.slice(0, 100)}"`);
    }
  }
  const html = read(join(SRC, '../index.html'));
  const metas = html.match(/<meta[^>]+description[^>]+>/g) || [];
  for (const m of metas) if (HIDDEN_TYPES.test(m)) found.push(`index.html: ${m.slice(0, 100)}`);
  assert.deepEqual(found, [], `Hidden types still sold:\n${found.join('\n')}`);
});
