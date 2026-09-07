/**
 * planLabels — the room-area labels the plan lane read but no room claimed
 * (`_meta.plan_area_lane.unclaimed`, extractor/plan_area_annotations.py): rooms
 * the model never returned. Each can become a room with one click; the room
 * carries the label as its area (read, not guessed) and sits where the label
 * stands, so the sheet can frame it. Perimeter and purpose stay unknown until
 * the contractor sets them — the engine marks what it assumed.
 *
 * Pure: no React, no DOM. Covered by planLabels.test.js.
 */

const nr = (v) => String(v ?? '').trim();

/** Unclaimed labels not yet turned into a room (matched by page + value). */
export function unclaimedPlanLabels(project) {
  const lane = project?._meta?.plan_area_lane;
  const list = Array.isArray(lane?.unclaimed) ? lane.unclaimed : [];
  const taken = new Set((project?.patalpos || [])
    .map((r) => r?._plotas_uzrasas)
    .filter(Boolean)
    .map((u) => `${u.page}|${Number(u.value_m2)}`));
  return list
    .filter((u) => u && Number.isFinite(Number(u.value_m2)) && Number(u.value_m2) > 0)
    .filter((u) => !taken.has(`${u.page}|${Number(u.value_m2)}`));
}

/** The next free room number in the project's own style (zero-padded like the rest). */
export function nextRoomNr(rooms) {
  const nrs = (rooms || []).map((r) => nr(r?.nr)).filter(Boolean);
  const numeric = nrs.map((s) => Number(s)).filter((n) => Number.isFinite(n));
  const width = Math.max(2, ...nrs.filter((s) => /^\d+$/.test(s)).map((s) => s.length));
  const next = (numeric.length ? Math.max(...numeric) : 0) + 1;
  return String(next).padStart(width, '0');
}

/** A new room built from one unclaimed label. */
export function roomFromPlanLabel(project, label) {
  const rooms = project?.patalpos || [];
  const W = Number(label.page_width); const H = Number(label.page_height);
  let bbox_pct = null;
  if (Array.isArray(label.bbox) && label.bbox.length === 4 && W > 0 && H > 0) {
    const cx = (Number(label.bbox[0]) + Number(label.bbox[2])) / 2 / W;
    const cy = (Number(label.bbox[1]) + Number(label.bbox[3])) / 2 / H;
    const half = 0.06;
    const c = (v) => Math.min(1, Math.max(0, v));
    bbox_pct = { x0: c(cx - half), y0: c(cy - half), x1: c(cx + half), y1: c(cy + half) };
  }
  const roomNr = nextRoomNr(rooms);
  return {
    nr: roomNr,
    pavadinimas: `Patalpa ${roomNr}`,
    paskirtis: null,
    plotas_m2: Number(label.value_m2),
    plotas_saltinis: 'plano_uzrasas',
    _plotas_uzrasas: {
      page: label.page, value_m2: Number(label.value_m2), bbox: label.bbox,
      page_width: label.page_width, page_height: label.page_height,
    },
    _prideta_is_plano: true,
    puslapio_nr: label.page ?? null,
    ...(bbox_pct ? { bbox_pct } : {}),
    elementai: [],
  };
}


/**
 * The rectangle (page-percent) that holds every plan label the rooms carry on
 * `page` — i.e. the drawn plan itself — with a margin, or null when fewer than
 * three labels sit on that page. Used to crop the „plane užrašytų plotų suma"
 * row to the plan instead of the whole sheet's white margins.
 */
export function planLabelsUnionRect(project, page, margin = 0.04) {
  const boxes = (project?.patalpos || [])
    .map((r) => r?._plotas_uzrasas)
    .filter((u) => u && Number(u.page) === Number(page) && Array.isArray(u.bbox) && u.bbox.length === 4
      && Number(u.page_width) > 0 && Number(u.page_height) > 0);
  if (boxes.length < 3) return null;
  const W = Number(boxes[0].page_width); const H = Number(boxes[0].page_height);
  let x0 = 1; let y0 = 1; let x1 = 0; let y1 = 0;
  for (const u of boxes) {
    x0 = Math.min(x0, Number(u.bbox[0]) / W); y0 = Math.min(y0, Number(u.bbox[1]) / H);
    x1 = Math.max(x1, Number(u.bbox[2]) / W); y1 = Math.max(y1, Number(u.bbox[3]) / H);
  }
  const c = (v) => Math.round(Math.min(1, Math.max(0, v)) * 1e4) / 1e4;
  return [c(x0 - margin), c(y0 - margin), c(x1 + margin), c(y1 + margin)];
}
