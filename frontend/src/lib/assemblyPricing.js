/**
 * assemblyPricing — price a sąmata from his „rinkiniai" (togal-v2 W9).
 *
 * An assembly lists what one unit of a work row is made of: labour
 * (`darbas`), machinery (`mechanizmai`) and materials (`medziaga`), each with
 * a norm per unit of the row, a waste % and a unit price. Applying it:
 *
 *   - the WORK row gets `kaina_darbo` = Σ labour + machinery (norma × (1 +
 *     atliekos) × kaina), and `kaina = kaina_darbo + kaina_medziagu`,
 *     `kaina_source: 'rinkinys'`, `rinkinys_id`;
 *   - a MATERIAL component prices the „Medžiagos" row the engine already wrote
 *     for that work (`susijes_darbas` = the work's label, same name) at the
 *     component's price per material unit — the row's quantity is never
 *     touched;
 *   - only a material component with NO Medžiagos row goes into the work row's
 *     `kaina_medziagu` (and its name into `medziagos_kainoje`, so the export
 *     can warn if such a row appears and gets priced later);
 *   - never both for one component, and nothing is ever zeroed: a Medžiagos
 *     row that already carries his own or a kainynas price is left alone and
 *     reported („palikta jūsų kaina").
 *
 * `suma = kiekis × kaina` stays the one formula: every exporter keeps reading
 * `kaina`; the split is extra information for the internal copy.
 *
 * Binding: the row's `rinkinys_id`, else an id listed in `taikoma.eilutes_id`,
 * else the kainynas matcher (`bestMatchForPozicija`, with its unit, sibling and
 * ambiguity guards) over `taikoma.aprasymas`. Pure — never mutates its input.
 */

// Explicit .js extension so this module also resolves under plain `node --test`.
import { bestMatchForPozicija } from './applyPriceList.js';
import { SK_MEDZIAGOS, SPLIT_CLEARED, isMaterialRow, round2 } from './priceSplit.js';

export { SK_MEDZIAGOS, SPLIT_CLEARED, isMaterialRow, round2 };

export const RINKINYS_SOURCE = 'rinkinys';
const KEPT_SOURCES = new Set(['manual', 'kainynas']);

const num = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
};

/** One component's cost per unit of the WORK row. */
export function componentUnitCost(c) {
  return num(c?.norma) * (1 + num(c?.atliekos_proc) / 100) * num(c?.kaina);
}

export function hasPrices(assembly) {
  return (assembly?.komponentai || []).some((c) => num(c?.kaina) > 0);
}

/** Labour + machinery + every material, per unit of the work row — what the
 *  assembly would cost if nothing were priced elsewhere. Used as the
 *  matcher's „price" (two candidates at different totals are ambiguous). */
export function assemblyUnitPrice(assembly) {
  return round2((assembly?.komponentai || []).reduce((s, c) => s + componentUnitCost(c), 0));
}

/** `{vieta}` part of `label` for a template label, '' for a plain one, null
 *  when it does not fit. Twin of api/sudetis.match_template. */
export function matchTemplate(template, label) {
  const t = String(template || '');
  const l = String(label || '').trim();
  const parts = t.split('{vieta}');
  if (parts.length === 1) return t === l ? '' : null;
  if (parts.length > 2) return null;
  const [pre, post] = parts;
  if (l.length < pre.length + post.length || !l.startsWith(pre) || !l.endsWith(post)) return null;
  return l.slice(pre.length, l.length - post.length);
}

function labelOf(row) {
  return String(row?.aprasymas || row?.pavadinimas || '').trim();
}

function materialNameMatches(name, rowLabel) {
  const lab = String(rowLabel || '').trim();
  return lab === name || lab.startsWith(`${name} — `);
}

/** Which assembly prices this row. `{ assembly, vieta }`, `{ ambiguous }` or null. */
export function assemblyForRow(row, assemblies) {
  const list = Array.isArray(assemblies) ? assemblies : [];
  const label = labelOf(row);
  const fit = (a) => {
    const v = matchTemplate(a?.taikoma?.aprasymas, label);
    return { assembly: a, vieta: v ?? '' };
  };
  if (row?.rinkinys_id) {
    const a = list.find((x) => x.id === row.rinkinys_id);
    if (a) return fit(a);
  }
  const byId = list.find((a) => (a?.taikoma?.eilutes_id || []).includes(row?.id));
  if (byId) return fit(byId);
  const templated = list.find((a) => String(a?.taikoma?.aprasymas || '').includes('{vieta}')
    && matchTemplate(a.taikoma.aprasymas, label) !== null);
  if (templated) return fit(templated);
  const candidates = list
    .filter((a) => a?.taikoma?.aprasymas && !String(a.taikoma.aprasymas).includes('{vieta}'))
    .map((a) => ({
      aprasymas: a.taikoma.aprasymas,
      vnt: a.taikoma.vnt || a.vnt || '',
      kaina: assemblyUnitPrice(a),
      _assembly: a,
    }));
  const m = bestMatchForPozicija(row, candidates);
  if (!m) return null;
  if (m.ambiguous) return { ambiguous: true, candidates: m.candidates };
  return { assembly: m.item._assembly, vieta: '' };
}

/**
 * Apply assemblies across a project's rows. Returns
 * `{ items, applied, materialsPriced, kept[], ambiguous[], skipped }` where
 * `kept` names the Medžiagos rows left at his own / kainynas price.
 *
 * options.overwriteManual — re-price hand-typed work rows too (UI never does).
 */
export function applyAssembliesToPositions(rows, assemblies, options = {}) {
  const src = Array.isArray(rows) ? rows : [];
  const priced = (Array.isArray(assemblies) ? assemblies : []).filter(hasPrices);
  const out = src.map((r) => r);
  const kept = [];
  const ambiguous = [];
  let applied = 0;
  let materialsPriced = 0;
  let skipped = 0;

  src.forEach((row, i) => {
    if (isMaterialRow(row)) return;
    if (row?.kaina_source === 'manual' && !options.overwriteManual) { skipped += 1; return; }
    const hit = assemblyForRow(row, priced);
    if (!hit) return;
    if (hit.ambiguous) {
      ambiguous.push({ aprasymas: labelOf(row), candidates: hit.candidates });
      return;
    }
    const { assembly, vieta } = hit;
    const label = labelOf(row);
    let darbo = 0;
    let medziagu = 0;
    const inRow = [];
    let touchedWork = false;
    for (const c of assembly.komponentai || []) {
      if (!(num(c?.kaina) > 0)) continue;
      if (c.rusis !== 'medziaga') {
        darbo += componentUnitCost(c);
        touchedWork = true;
        continue;
      }
      const name = String(c.pavadinimas || '').replaceAll('{vieta}', vieta);
      const j = src.findIndex((m) => isMaterialRow(m)
        && String(m?.susijes_darbas || '').trim() === label
        && materialNameMatches(name, labelOf(m)));
      if (j >= 0) {
        const m = out[j];
        if (num(m.kaina) > 0 && KEPT_SOURCES.has(m.kaina_source)) {
          kept.push({ aprasymas: labelOf(m), kaina: num(m.kaina) });
          continue;
        }
        const k = num(c.kaina);
        out[j] = {
          ...m,
          kaina: k,
          suma: num(m.kiekis) * k,
          kaina_source: RINKINYS_SOURCE,
          kaina_match_score: undefined,
          rinkinys_id: assembly.id,
        };
        materialsPriced += 1;
      } else {
        medziagu += componentUnitCost(c);
        inRow.push(name);
        touchedWork = true;
      }
    }
    if (!touchedWork) return;
    const kaina_darbo = round2(darbo);
    const kaina_medziagu = round2(medziagu);
    const kaina = round2(kaina_darbo + kaina_medziagu);
    out[i] = {
      ...out[i],
      kaina,
      suma: num(row.kiekis) * kaina,
      kaina_darbo,
      kaina_medziagu,
      medziagos_kainoje: inRow.length ? inRow : undefined,
      kaina_source: RINKINYS_SOURCE,
      kaina_match_score: undefined,
      rinkinys_id: assembly.id,
    };
    applied += 1;
  });
  return { items: out, applied, materialsPriced, kept, ambiguous, skipped };
}

/**
 * Why a „Medžiagos" row carries no price of its own: its work row's price
 * already includes it (a kainynas material column, or a rinkinys material with
 * no row of its own at the time). `Map<materialRowIndex, note>` — derived from
 * the work rows on every render, never stored, so it cannot go stale.
 */
export function materialPriceNotes(rows) {
  const list = Array.isArray(rows) ? rows : [];
  const notes = new Map();
  for (const w of list) {
    if (isMaterialRow(w) || !Array.isArray(w?.medziagos_kainoje) || !(num(w.kaina_medziagu) > 0)) continue;
    const label = labelOf(w);
    list.forEach((m, j) => {
      if (!isMaterialRow(m) || String(m?.susijes_darbas || '').trim() !== label) return;
      if (!w.medziagos_kainoje.some((name) => materialNameMatches(name, labelOf(m)))) return;
      notes.set(j, `Medžiagų kaina įskaičiuota į „${label}“ darbo eilutę`);
    });
  }
  return notes;
}

/**
 * The export guard: a material whose price sits inside a work row's
 * `kaina_medziagu` AND on a priced Medžiagos row (one that appeared or was
 * priced after the assembly was applied) is billed twice. Returns
 * `[{ darbas, medziaga }]`.
 */
export function doubleBilledMaterials(rows) {
  const list = Array.isArray(rows) ? rows : [];
  const out = [];
  for (const w of list) {
    if (isMaterialRow(w) || !Array.isArray(w?.medziagos_kainoje) || !(num(w.kaina_medziagu) > 0)) continue;
    const label = labelOf(w);
    for (const name of w.medziagos_kainoje) {
      const m = list.find((x) => isMaterialRow(x)
        && String(x?.susijes_darbas || '').trim() === label
        && materialNameMatches(name, labelOf(x)) && num(x.kaina) > 0);
      if (m) out.push({ darbas: label, medziaga: labelOf(m) });
    }
  }
  return out;
}
