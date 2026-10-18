/**
 * csvSafe.js — a CSV cell that a spreadsheet will show as text, never run as a
 * formula (audit backend-security-4, 2026-10-18; the backend twin is
 * backend/extractor/spreadsheet_safety.py).
 *
 * A cell starting with = + - @ (or a tab / carriage return) is a formula to
 * Excel and LibreOffice; room names, row descriptions and warnings are typed or
 * read off a drawing, so they get a leading apostrophe. A plain number
 * („-1,5", „12.40") is left alone.
 */
const FORMULA_START = /^[=+\-@\t\r]/;
const PLAIN_NUMBER = /^-?\d[\d\s.,]*$/;

export function csvSafe(value) {
  const s = value == null ? '' : String(value);
  if (FORMULA_START.test(s) && !PLAIN_NUMBER.test(s)) return `'${s}`;
  return s;
}
