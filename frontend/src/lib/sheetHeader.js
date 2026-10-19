// sheetHeader — what the viewer's header card says about the sheet on screen (Pathon v3 W5-B, B1; coverage #8, #9).
//
// The header names the sheet the way the drawing does: its badge (the sheet number written in the title block,
// „B.01", else the page number), its name („Išdėstymo planas") and where it is in the set: „← 1 iš 8 →".
// PageUp / PageDown and the arrows step one sheet (lib/viewerShortcuts nextPage / prevPage). Pure — the sheet
// names come from lib/sheetRail.buildSheetRail, the component is components/viewer/SheetHeaderBadge.jsx.

/** The badge text: the short sheet number when it is short enough for a chip, else the page number. */
export function sheetBadge(sheet, page) {
  const tag = String(sheet?.shortNumber || '').trim();
  if (tag && tag.length <= 8) return tag;
  return String(page);
}

/**
 * The header for `page` of `total` → { page, total, badge, name, title, pager, canPrev, canNext, prev, next }.
 *   name   the sheet's own name without its number („Išdėstymo planas"); „Lapas 3" when the set is unnamed;
 *   title  the full line for the tooltip and the screen reader („Lapas 3 iš 8: B.01 Išdėstymo planas");
 *   pager  „3 iš 8".
 */
export function sheetHeaderModel({ page, total, sheets = null } = {}) {
  const n = Math.max(1, Number(total) || 1);
  const p = Math.min(n, Math.max(1, Number(page) || 1));
  const sheet = Array.isArray(sheets) ? sheets.find((s) => Number(s?.page) === p) || null : null;
  const badge = sheetBadge(sheet, p);
  const name = String(sheet?.name || '').trim() || `Lapas ${p}`;
  const full = String(sheet?.fullName || '').trim();
  return {
    page: p,
    total: n,
    badge,
    name,
    title: `Lapas ${p} iš ${n}${full && full !== name ? `: ${full}` : (name !== `Lapas ${p}` ? `: ${name}` : '')}`,
    pager: `${p} iš ${n}`,
    canPrev: p > 1,
    canNext: p < n,
    prev: Math.max(1, p - 1),
    next: Math.min(n, p + 1),
  };
}
