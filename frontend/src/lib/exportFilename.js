/**
 * sanitizeExportFilename — turn a project name into a safe download filename.
 *
 * The old inline `replace(/[^\w\s-]/g, '')` was ASCII-only, so every Lithuanian
 * letter was silently deleted: "Beržų g. 24" downloaded as "Ber g 24". \p{L}
 * keeps letters of any script (and \p{N} any digit), while the blacklist of
 * filesystem-hostile characters (/ \ : * ? " < > | and control chars) still
 * goes. Dots and dashes are kept on purpose — "Beržų g. 24" reads wrong
 * without them. (2026-07-28 UX walkthrough.)
 */
export function sanitizeExportFilename(name, fallback = 'projektas') {
  const cleaned = String(name ?? '')
    // Drop anything that is not a letter, digit, space, dot, underscore or dash.
    .replace(/[^\p{L}\p{N}\s._-]/gu, '')
    // Collapse the whitespace the removals leave behind (incl. NBSP).
    .replace(/\s+/gu, ' ')
    // A leading dot would make a hidden file; trailing dots/spaces are stripped
    // by Windows anyway.
    .replace(/^[.\s]+/, '')
    .replace(/[.\s]+$/, '');
  return cleaned || fallback;
}

export default sanitizeExportFilename;
