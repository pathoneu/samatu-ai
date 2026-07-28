/**
 * parseLtNumber — parse a Lithuanian-formatted number typed by a user.
 *
 * LT keyboards/locale use a COMMA as the decimal separator and a space (or a
 * dot) as the thousands separator, so `parseFloat('12,5')` silently returns 12
 * and `parseFloat('1 234,56')` returns 1. Every numeric input in the app must
 * go through this helper instead.
 *
 * Rules:
 *   - all whitespace (incl. NBSP U+00A0 / narrow NBSP U+202F) is stripped
 *   - one comma, no dot          → comma is the decimal point ('12,5' → 12.5)
 *   - one comma + dots           → dots are thousands ('1.234,56' → 1234.56)
 *   - no comma, several dots     → dots are thousands ('1.234.567' → 1234567)
 *   - no comma, one dot          → plain decimal ('12.5' → 12.5)
 *   - anything else (2+ commas, letters, empty) → NaN
 *
 * Returns a Number, or NaN when the input is not a valid number. Callers must
 * check with Number.isFinite() and reject invalid input explicitly — never
 * fall back to 0.
 */
export function parseLtNumber(input) {
  if (typeof input === 'number') return Number.isFinite(input) ? input : NaN;
  if (input == null) return NaN;

  // Strip every space-ish character used as a thousands separator.
  let s = String(input).replace(/[\s   ]/g, '');
  if (!s) return NaN;

  const commas = (s.match(/,/g) || []).length;
  const dots = (s.match(/\./g) || []).length;

  if (commas > 1) return NaN;              // '12,5,6' — not a number
  if (commas === 1 && dots === 0) {
    s = s.replace(',', '.');               // '12,5'
  } else if (commas === 1) {
    s = s.replace(/\./g, '').replace(',', '.');  // '1.234,56'
  } else if (dots > 1) {
    s = s.replace(/\./g, '');              // '1.234.567'
  }

  // Reject exponents, stray signs, units — anything that isn't a plain decimal.
  if (!/^[+-]?(\d+(\.\d*)?|\.\d+)$/.test(s)) return NaN;
  return Number(s);
}

/**
 * Upper bound for a kiekis / kaina input (99 999 999).
 *
 * There was no ceiling at all: 999999999999 × 1000000 was accepted and the
 * sąmata printed a nonsense 10^18 € total. Nothing in LT interior work is
 * bigger than ~10^8 of anything, so treat a larger number as a typo (a missed
 * decimal separator or a pasted phone number) and reject it like any other
 * invalid input — never clamp silently. (2026-07-28 UX walkthrough.)
 */
export const MAX_AMOUNT = 99_999_999;

/** True when `n` is a finite, non-negative amount within MAX_AMOUNT. */
export function isValidAmount(n) {
  return Number.isFinite(n) && n >= 0 && n <= MAX_AMOUNT;
}

export default parseLtNumber;
