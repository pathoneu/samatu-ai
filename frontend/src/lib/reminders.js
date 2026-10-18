/**
 * Reminders (Pathon v3 W5-E, E8 + E9) — the pure half: which of the project's reminders a screen shows, and
 * what the one-line head says. The list comes from `GET /api/projects/{id}/reminders`
 * (backend/extractor/reminders.py); every item is a plain Lithuanian sentence, never a quantity row.
 */
export const WHERE_PATIKRA = 'patikra';
export const WHERE_SAMATA = 'samata';
// Shown before „Rodyti visus (N)": the reminders that point at the drawing or warn first.
export const VISIBLE_FIRST = 1;

/** The reminders meant for one screen, warnings first, in the server's order otherwise. */
export function remindersFor(list, where) {
  const items = (Array.isArray(list) ? list : []).filter(
    (r) => r && typeof r.sentence === 'string' && r.sentence && (!Array.isArray(r.vieta) || r.vieta.includes(where)));
  const rank = (r) => (r.tone === 'warning' ? 0 : 1);
  return items.map((r, i) => [r, i]).sort((a, b) => rank(a[0]) - rank(b[0]) || a[1] - b[1]).map(([r]) => r);
}

/** „priminimas / priminimai / priminimų" — LT number agreement. */
export function remindersWord(n) {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (b === 1 && a !== 11) return 'priminimas';
  if (b >= 2 && b <= 9 && !(a >= 12 && a <= 19)) return 'priminimai';
  return 'priminimų';
}

/** Where „Rodyti brėžinyje" goes, or null when the reminder has no place on the drawing. */
export function evidenceTarget(r) {
  const e = r?.evidence;
  const page = Number(e?.page);
  if (!e || !Number.isFinite(page) || page < 1) return null;
  const rect = Array.isArray(e.rect_pct) && e.rect_pct.length === 4 && e.rect_pct.every(Number.isFinite)
    ? e.rect_pct : null;
  return { page, rect_pct: rect };
}
