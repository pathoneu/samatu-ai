/**
 * newProjectForm — what the New Project form sends with an interior reading and
 * the four fields it adds to the project: „Projekto pavadinimas", „Įmonės
 * pavadinimas", „Koks objektas?" and „Lubų aukštis, jei žinote".
 *
 * A new interior project is saved by one of two hands:
 *   • the BROWSER, when the stream delivers the result (NewProject.jsx →
 *     createProject);
 *   • the SERVER, when the stream went first — Railway cuts it at ~10-15 min
 *     and a real reading takes ~20 (backend/main.py `_save_orphaned_result`).
 * Until 2026-10-07 the server knew none of the four: a contractor who typed
 * „Testo g. 1 butas" found his project named after the PDF, no company and his
 * ceiling height gone. Both hands now take them from `projectMeta`, and the
 * backend applies the same limits (`_project_meta`), so both store the same.
 *
 * Pure: no React, no i18n. Covered by newProjectForm.test.js. Relative import
 * with .js: this module runs under `node --test`, which resolves no Vite aliases.
 */
import { parseLtNumber } from './parseLtNumber.js';

/** Longest name / company kept — the inputs' maxLength, the backend's cut. */
export const META_TEXT_MAX = 200;
/** „Koks objektas?" — the form's three answers. */
export const OBJEKTAS_TIPAI = ['butas', 'namas', 'komercines'];
// The height window of Nustatymai's „Visos patalpos" field (AssumptionsPanel
// H_MIN_M / H_MAX_M): a default outside it could never be applied from there.
export const CEILING_DEFAULT_MIN_M = 2.0;
export const CEILING_DEFAULT_MAX_M = 6.0;

const text = (v) => (typeof v === 'string' ? v.trim().slice(0, META_TEXT_MAX) : '');

/**
 * The four fields from what he typed and chose. `name` is '' when he typed
 * none: each hand then falls back the same way — the reading's own title, then
 * a default (the browser) or the PDF's name (the server). The ceiling height is
 * kept only as a number Nustatymai would accept.
 *
 * @returns {{name: string, company_name: string, objektas_tipas?: string,
 *            lubu_aukstis_default_m?: number}}
 */
export function projectMeta({ name, companyName, objektas, ceilingHeight } = {}) {
  const meta = { name: text(name), company_name: text(companyName) };
  if (OBJEKTAS_TIPAI.includes(objektas)) meta.objektas_tipas = objektas;
  const h = parseLtNumber(ceilingHeight);
  if (Number.isFinite(h) && h >= CEILING_DEFAULT_MIN_M && h <= CEILING_DEFAULT_MAX_M) {
    meta.lubu_aukstis_default_m = h;
  }
  return meta;
}

/**
 * The POST /extract-interior-stream body of a NEW project: the PDF, the
 * subtype, the rules override (Setup Wizard preferences + „ką skaičiuoti",
 * built by the caller; null = none) and `project_meta` — the four fields, for
 * the server to save with the project should the stream go first.
 */
export function interiorStreamForm(file, { interiorSubtype, rulesOverride = null, meta = null } = {}) {
  const fd = new FormData();
  fd.append('files', file);
  fd.append('interior_subtype', interiorSubtype || 'naujas');
  if (rulesOverride) fd.append('rules_override', JSON.stringify(rulesOverride));
  if (meta) fd.append('project_meta', JSON.stringify(meta));
  return fd;
}

/**
 * The form's fields a project the SERVER saved does not carry — {} when it has
 * them all. A server that did not apply `project_meta` (a backend older than
 * this page, while a deploy rolls out) named the project after the PDF; the
 * caller writes these back, so a recovered project never keeps a name other
 * than the one he typed. Nothing typed, nothing to restore.
 */
export function metaToRestore(project, meta) {
  const out = {};
  if (!project || !meta) return out;
  for (const key of ['name', 'company_name', 'objektas_tipas', 'lubu_aukstis_default_m']) {
    const want = meta[key];
    if (want !== undefined && want !== null && want !== '' && project[key] !== want) out[key] = want;
  }
  return out;
}
