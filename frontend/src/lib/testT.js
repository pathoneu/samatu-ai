/**
 * testT — i18next's `t` contract over the real catalogues, for the node:test units of pure libs that take `t`
 * (lib/scaleProvenance and its callers). Dotted lookup, `{{name}}` interpolation, and plural suffixes picked by
 * Intl.PluralRules (one · few · many · other, falling back to `_other`, then the bare key) — what i18next does.
 * A missing key returns the key itself, so a test sees it. Not imported by the app.
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));

export function makeT(lang = 'lt') {
  const catalogue = JSON.parse(readFileSync(join(HERE, `../i18n/${lang}.json`), 'utf8'));
  const rules = new Intl.PluralRules(lang);
  const find = (key) => key.split('.').reduce((node, k) => (node && typeof node === 'object' ? node[k] : undefined), catalogue);
  return (key, params = {}) => {
    let value;
    if (typeof params.count === 'number') {
      value = find(`${key}_${rules.select(params.count)}`) ?? find(`${key}_other`);
    }
    value ??= find(key);
    if (typeof value !== 'string') return key;
    return value.replace(/\{\{\s*(\w+)\s*\}\}/g, (_, name) => (params[name] == null ? '' : String(params[name])));
  };
}
