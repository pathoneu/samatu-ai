/**
 * vatMode.js — is the 21 % PVM line on? One rule for every on-screen total
 * and every export. Twin of backend `extractor/vat_mode.py`; keep them in step.
 *
 *   vat_mode 'standard'     21 % PVM is added — even when the drawing label
 *                           says „renovacija".
 *   vat_mode 'reverse_vat'  atvirkštinis PVM (PVMĮ 96 str.): the customer
 *                           accounts for it, no PVM line.
 *   absent / anything else  the old rule, unchanged for stored projects:
 *                           reverse only when `archetipas` is „renovacija".
 *
 * `archetipas` is read off the drawing, not chosen by the contractor — so the
 * export dialog says when the mode came from it and asks him to check
 * (audit 2026-09-29, exports-money-2).
 */

export const VAT_STANDARD = 'standard';
export const VAT_REVERSE = 'reverse_vat';

function explicitMode(project) {
  const m = String(project?.vat_mode || '').toLowerCase();
  return m === VAT_STANDARD || m === VAT_REVERSE ? m : null;
}

/** True when the document carries no PVM line. */
export function isReverseVat(project) {
  const m = explicitMode(project);
  if (m) return m === VAT_REVERSE;
  return String(project?.archetipas || '').toLowerCase() === 'renovacija';
}

/**
 * The mode that will be printed, and whether it came from the drawing label
 * rather than from him (only reverse VAT can: the default is 21 %).
 */
export function vatChoice(project) {
  const m = explicitMode(project);
  if (m) return { mode: m, fromLabel: false };
  const reverse = isReverseVat(project);
  return { mode: reverse ? VAT_REVERSE : VAT_STANDARD, fromLabel: reverse };
}

/** The rates he can pick (Settings, the export dialog). Twin of backend VAT_RATES. */
export const VAT_RATES = Object.freeze([21, 9, 0]);
export const DEFAULT_VAT_RATE = 21;

/** A rate out of any stored value: 21 / 9 / 0 when it is one, else null. */
export function parseVatRate(value) {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null;
  const n = Number(String(value).replace('%', '').replace(',', '.').trim());
  return Number.isFinite(n) && VAT_RATES.includes(n) ? n : null;
}

/**
 * The project's PVM rate (v3 M4, 2026-10-18). 0 % is a real choice — the old
 * `vat_rate || 21` turned it back into 21. A project with no valid rate takes
 * the account default (`fallback`, Settings › PVM tarifas), else 21.
 */
export function vatRateOf(project, fallback = DEFAULT_VAT_RATE) {
  return parseVatRate(project?.vat_rate) ?? parseVatRate(fallback) ?? DEFAULT_VAT_RATE;
}

/** The PVM percent a total adds: 0 under reverse VAT, else the project's rate. */
export function vatPercent(project) {
  return isReverseVat(project) ? 0 : vatRateOf(project);
}
