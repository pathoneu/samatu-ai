/**
 * kodas — the cost code a sąmata row prints (togal-v2 W9).
 *
 * His typed code first; then the code of the rinkinys he bound the row to;
 * then the default family whose label template matches the engine's label;
 * then the section's code (`kodai`, served by GET /api/assemblies from the
 * backend's SKYRIUS_KODAI — one table). Twin of api/sudetis.effective_kodas:
 * both run the cases in kodas.cases.json.
 */

// Explicit .js extension so this module also resolves under plain `node --test`.
import { matchTemplate } from './assemblyPricing.js';
import { isMaterialRow } from './priceSplit.js';

/** Section name → skyrius_enum for rows saved before the enum existed.
 *  Mirror of the engine's `_SKYRIUS_ENUM` (backend/extractor/vision_call.py). */
const SKYRIUS_ENUM = {
  'GKP montavimas': 'gkp',
  'Sienų lubų glaistymas dažymas': 'paint',
  'Sienų glaistymas dažymas': 'paint',
  'Lubų glaistymas dažymas': 'paint',
  'Plytelių klijavimas': 'tile',
  Hidroizoliacija: 'waterproof',
  Grindys: 'floor',
  'Santechnikos darbai': 'plumbing',
  'Elektros instaliacijos darbai': 'electrical',
  'Pridėtiniai elementai': 'extras',
  Medžiagos: 'materials',
  'Out of scope': 'out_of_scope',
};

export function effectiveKodas(row, assemblies = [], kodai = {}) {
  const typed = typeof row?.kodas === 'string' ? row.kodas.trim() : '';
  if (typed) return typed;
  const list = Array.isArray(assemblies) ? assemblies : [];
  const label = String(row?.aprasymas || row?.pavadinimas || '');
  const material = isMaterialRow(row);
  if (row?.rinkinys_id && !material) {
    const a = list.find((x) => x?.id === row.rinkinys_id);
    if (a?.kodas) return a.kodas;
  }
  if (!material) {
    const d = list.find((a) => a?.is_default && matchTemplate(a?.taikoma?.aprasymas, label) !== null);
    if (d?.kodas) return d.kodas;
  }
  const en = row?.skyrius_enum || SKYRIUS_ENUM[String(row?.skyrius || '')] || 'extras';
  return kodai?.[en] ?? null;
}
