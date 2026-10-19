// sheetZonesView — what the viewer shows of a sheet's zones (Pathon v3 W5-B, B2; coverage #11; design §4A
// „the viewer: zone outline on hover"). The zones come from GET …/pages/{page}/zones (lib/sheetZonesApi).
//
// At rest nothing is drawn. Hovering a legend, a table, the title block or a notes block outlines it and
// names it („Legenda", „Lentelė · DURŲ ŽINIARAŠTIS"); the plan itself is never outlined on hover (it is most of
// the sheet). „Rodyti sritis" in the view settings draws every zone, the plan included — the way to see them
// without hovering (Rimas: nothing hover-only). Pure.

export const ZONE_NAMES = Object.freeze({
  planas: 'Planas',
  legenda: 'Legenda',
  lentele: 'Lentelė',
  antspaudas: 'Antspaudas',
  pastabos: 'Pastabos',
  kita: 'Neaiški sritis',
});

const LABEL_MAX = 40;
const PRIORITY = { antspaudas: 0, lentele: 1, legenda: 2, pastabos: 3, kita: 4, planas: 5 };

const area = (b) => Math.max(0, b[2] - b[0]) * Math.max(0, b[3] - b[1]);
const valid = (z) => Array.isArray(z?.bbox_pct) && z.bbox_pct.length === 4 && ZONE_NAMES[z.kind];

/** „Lentelė · DURŲ ŽINIARAŠTIS" — the kind, then the zone's own title when it has one (shortened). */
export function zoneLabel(zone) {
  const name = ZONE_NAMES[zone?.kind] || ZONE_NAMES.kita;
  let own = String(zone?.label || '').replace(/\s+/g, ' ').trim();
  if (!own || own.toLowerCase() === name.toLowerCase()) return name;
  if (own.length > LABEL_MAX) own = `${own.slice(0, LABEL_MAX - 1).trimEnd()}…`;
  return `${name} · ${own}`;
}

/**
 * The zone a hover at (x, y) names: the innermost zone that is not a plan (the backend's zone_at order: the
 * smallest wins, ties by kind). The plan is never a hover target. Null when the point is in no such zone.
 */
export function hoverZoneAt(zones, x, y) {
  const hits = (Array.isArray(zones) ? zones : []).filter((z) => valid(z) && z.kind !== 'planas'
    && x >= z.bbox_pct[0] && x <= z.bbox_pct[2] && y >= z.bbox_pct[1] && y <= z.bbox_pct[3]);
  if (!hits.length) return null;
  hits.sort((a, b) => area(a.bbox_pct) - area(b.bbox_pct) || (PRIORITY[a.kind] ?? 9) - (PRIORITY[b.kind] ?? 9));
  return hits[0];
}

/** What to draw: every valid zone while „Rodyti sritis" is on, else the hovered one (or nothing). */
export function zonesToDraw(zones, { shown = false, hovered = null } = {}) {
  const list = (Array.isArray(zones) ? zones : []).filter(valid);
  if (shown) return list;
  return hovered && list.includes(hovered) ? [hovered] : [];
}
