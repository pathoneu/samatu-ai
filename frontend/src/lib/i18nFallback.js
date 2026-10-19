/**
 * Last line of defence for translations (2026-10-19, Safari walk): a key must NEVER reach the screen.
 *
 * i18next calls `parseMissingKeyHandler(key, defaultValue, options)` when neither the active language
 * nor the fallback resolved a key — normally it then shows the key itself („project.sanity.pillWarnings").
 * This handler looks the key up DIRECTLY in the Lithuanian catalogue (the imported JSON, not i18next's
 * store, which is what failed), applies the plural form and {{variables}}, and otherwise returns the
 * caller's default text or an empty string. Each unresolved key is reported once in the console so a
 * developer still sees it.
 */

const PLURAL_SUFFIXES = ['_zero', '_one', '_two', '_few', '_many', '_other'];

function nodeAt(catalogue, key) {
  let node = catalogue;
  for (const part of String(key).split('.')) {
    if (!node || typeof node !== 'object') return undefined;
    node = node[part];
  }
  return node;
}

function pluralForm(catalogue, key, count) {
  const dot = key.lastIndexOf('.');
  const parent = dot < 0 ? catalogue : nodeAt(catalogue, key.slice(0, dot));
  const leaf = key.slice(dot + 1);
  if (!parent || typeof parent !== 'object') return undefined;
  if (!PLURAL_SUFFIXES.some((s) => typeof parent[leaf + s] === 'string')) return undefined;
  let category = 'other';
  try {
    category = new Intl.PluralRules('lt').select(Number(count));
  } catch {
    /* no Intl — the _other form below */
  }
  if (Number(count) === 0 && typeof parent[`${leaf}_zero`] === 'string') return parent[`${leaf}_zero`];
  return parent[`${leaf}_${category}`] ?? parent[`${leaf}_other`] ?? parent[`${leaf}_many`];
}

/** `{{name}}` → options.name (escapeValue is off app-wide; React escapes). */
export function interpolate(text, options = {}) {
  return String(text).replace(/\{\{\s*([\w.]+)\s*\}\}/g, (whole, name) => {
    const v = name.split('.').reduce((o, p) => (o == null ? undefined : o[p]), options);
    return v == null ? '' : String(v);
  });
}

/**
 * The Lithuanian text for `key`, or undefined when the catalogue has none.
 * Strings get their plural form and variables; an object node is returned as is (the app sets
 * returnObjects globally, so i18next's per-call options do not carry it).
 */
export function lookupLithuanian(catalogue, key, options = {}) {
  if (!catalogue || typeof key !== 'string' || !key) return undefined;
  if (options && options.count !== undefined) {
    const form = pluralForm(catalogue, key, options.count);
    if (typeof form === 'string') return interpolate(form, options);
  }
  const node = nodeAt(catalogue, key);
  if (typeof node === 'string') return interpolate(node, options);
  if (node && typeof node === 'object') return node;
  return undefined;
}

const _reported = new Set();

/** Build the i18next `parseMissingKeyHandler` over the Lithuanian catalogue. */
export function makeMissingKeyHandler(catalogue, { warn = (m) => console.warn(m) } = {}) {
  return function parseMissingKeyHandler(key, defaultValue, options) {
    const found = lookupLithuanian(catalogue, key, options || {});
    if (found !== undefined) return found;
    if (typeof defaultValue === 'string' && defaultValue && defaultValue !== key) return defaultValue;
    if (!_reported.has(key)) {
      _reported.add(key);
      try { warn(`[i18n] no Lithuanian text for "${key}"`); } catch { /* console unavailable */ }
    }
    return '';
  };
}
