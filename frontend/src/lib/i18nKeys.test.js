import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

// Every literal translation key the code asks for must exist in the Lithuanian catalogue
// (2026-10-19, Safari walk: the founder saw raw keys such as „project.sanity.pillWarnings").
// A key that resolves only through plural suffixes (_one/_few/_many/_other) counts as present;
// so does an object node (t('…', { returnObjects: true })). Keys built at runtime
// (template literals with ${…}) cannot be checked here and are skipped.
const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = join(HERE, '..');
const lt = JSON.parse(readFileSync(join(SRC, 'i18n/lt.json'), 'utf8'));
const en = JSON.parse(readFileSync(join(SRC, 'i18n/en.json'), 'utf8'));

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(jsx?|tsx?)$/.test(name) && !/\.test\.js$/.test(name)) out.push(p);
  }
  return out;
}

// t('a.b'), t("a.b"), t(`a.b`), i18n.t('a.b'), i18nKey="a.b"; the key must contain a dot.
const CALL = /(?<![\w$.])(?:i18n\.)?t\(\s*(['"`])([A-Za-z][\w-]*(?:\.[\w-]+)+)\1/g;
const TRANS = /i18nKey=(?:\{\s*)?(['"`])([A-Za-z][\w-]*(?:\.[\w-]+)+)\1/g;
const PLURAL = ['_zero', '_one', '_two', '_few', '_many', '_other'];

export function lookup(catalogue, key) {
  const parts = key.split('.');
  const last = parts.pop();
  let node = catalogue;
  for (const p of parts) {
    node = node && typeof node === 'object' ? node[p] : undefined;
  }
  if (!node || typeof node !== 'object') return false;
  if (node[last] !== undefined) return true;
  return PLURAL.some((s) => node[last + s] !== undefined);
}

export function usedKeys() {
  const found = new Map();   // key -> first file
  for (const file of walk(SRC)) {
    const text = readFileSync(file, 'utf8');
    for (const re of [CALL, TRANS]) {
      for (const m of text.matchAll(re)) {
        if (!found.has(m[2])) found.set(m[2], relative(SRC, file));
      }
    }
  }
  return found;
}

const keys = usedKeys();

test('the scan finds the keys the app uses', () => {
  // Sanity floor: the app has hundreds of t() calls; a regex regression must not pass vacuously.
  assert.ok(keys.size > 500, `only ${keys.size} keys found`);
  assert.ok(keys.has('project.sanity.pillWarnings'));
});

test('every t() key exists in lt.json', () => {
  const missing = [...keys].filter(([k]) => !lookup(lt, k)).map(([k, f]) => `${k}  (${f})`);
  assert.deepEqual(missing, [], `keys missing from lt.json:\n${missing.join('\n')}`);
});

test('every t() key exists in en.json or falls back to Lithuanian', () => {
  // en.json is additive (public pages first); a key absent there falls back to lt — which the test
  // above guarantees. This one lists the keys that would show Lithuanian on the English page, and only
  // fails for keys that are in NEITHER catalogue.
  const neither = [...keys].filter(([k]) => !lookup(en, k) && !lookup(lt, k)).map(([k]) => k);
  assert.deepEqual(neither, []);
});

test('every runtime-built key lands in an existing catalogue node', () => {
  // t(`project.questions.${key}`): the static part before ${ must name an object in lt.json, so a renamed
  // or deleted group is caught even though the leaf is only known at runtime.
  const DYN = /(?<![\w$.])(?:i18n\.)?t\(\s*`([A-Za-z][\w.-]*)\$\{/g;
  const bad = [];
  for (const file of walk(SRC)) {
    for (const m of readFileSync(file, 'utf8').matchAll(DYN)) {
      const prefix = m[1].slice(0, m[1].lastIndexOf('.'));
      const node = prefix.split('.').reduce((n, p) => (n && typeof n === 'object' ? n[p] : undefined), lt);
      if (!node || typeof node !== 'object') bad.push(`${m[1]}…  (${relative(SRC, file)})`);
    }
  }
  assert.deepEqual(bad, []);
});

test('components take useTranslation from @/i18n/react, never react-i18next directly', () => {
  const direct = walk(SRC)
    .filter((f) => !relative(SRC, f).startsWith('i18n/'))
    .filter((f) => /from\s+['"]react-i18next['"]/.test(readFileSync(f, 'utf8')))
    .map((f) => relative(SRC, f));
  assert.deepEqual(direct, []);
});
