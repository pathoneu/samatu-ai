/**
 * roomTool — the viewer's room tool R (Pathon v3 wave 1, W1-D, D2; design §4 track D, §5 „Room (R)").
 *
 * One click inside a room → the wall-exact outline the room sheet's „Parodyti patalpą" gives
 * (`POST …/rooms/{nr}/outline-at` with `perziura`: read, nothing saved, no journal row) is PROPOSED on the
 * drawing with one consequence line; his next click elsewhere or Enter saves it through `outline-set`
 * (`kaip: "parodyta"`), Esc drops it. Review before it exists, and every save has its „Atšaukti".
 *
 * Which room he means is decided here, from what the project already knows — no extra request:
 *   1. the outline under the click (on this sheet, or laid over from another sheet of the same plan);
 *   2. else the room whose printed number (the lane's strong seat) is nearest on this plan;
 *   3. else nothing — the tool asks „Kuri tai patalpa?".
 * The server then has the last word: a click inside a NEIGHBOUR's trusted outline answers `taken` with that
 * room, a face that holds exactly one other room's number answers `open` with it — `retryNrFor` turns
 * either into ONE retry with the room the walls say it is.
 *
 * Kreo's „click outside expands, inside shrinks" needs seeds the vector reader does not take
 * (`vector_rooms.outline_at` reads the ONE face under one point), so a second click is a new room, not a
 * correction of this one — the limitation is written in the report and in the hint. Pure.
 */
import { ltNumber } from './ledger.js';
import { mapPct } from './checkOverlay.js';
import { pointInPolygonPoints, roomPageOf } from './roomZones.js';

const STRONG_SEATS = new Set(['zenkliukas', 'plotas_uzrasas']);
const NOT_TRACED = new Set(['synthesized_from_bbox', 'bbox_fallback', 'manual_needed']);

const num = (v) => (Number.isFinite(Number(v)) && v !== null && v !== '' ? Number(v) : null);

function ringOf(poly) {
  if (!Array.isArray(poly) || poly.length < 3) return null;
  const ring = poly.map((p) => [num(p?.[0]), num(p?.[1])]);
  return ring.every(([x, y]) => x != null && y != null) ? ring : null;
}

function area(ring) {
  let a = 0;
  for (let i = 0; i < ring.length; i += 1) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[(i + 1) % ring.length];
    a += x1 * y2 - x2 * y1;
  }
  return Math.abs(a / 2);
}

/** A room's outline laid onto `page` (display fractions), or null when it is on another plan / has none. */
function outlineOn(room, page, sutapdinimas) {
  const ring = NOT_TRACED.has(String(room?.polygon_source || '')) ? null : ringOf(room?.polygon_pct);
  if (!ring) return null;
  const from = num(room?._konturas?.page) ?? num(roomPageOf(room));
  if (from == null) return null;
  if (from === page) return ring;
  const laid = ring.map((pt) => mapPct(pt, from, page, sutapdinimas));
  // mapPct hands the point back unchanged when the sheets are not one plan: refuse that
  const same = laid.every((pt, i) => pt === ring[i]);
  return same ? null : laid;
}

/** The room's printed number on `page` (the lane's strong seat, laid over), or null. */
function seatOn(room, page, sutapdinimas) {
  const v = room?._vieta;
  if (!v || !STRONG_SEATS.has(v.saltinis)) return null;
  const x = num(v.cx);
  const y = num(v.cy);
  const from = num(v.page);
  if (x == null || y == null || from == null) return null;
  if (from === page) return [x, y];
  const pt = [x, y];
  const laid = mapPct(pt, from, page, sutapdinimas);
  return laid === pt ? null : laid;
}

/** Rooms a click can never be: merged into another, or not on any sheet. */
const pickable = (r) => r && r.nr != null && r?._konturas?.saltinis !== 'sujungta' && !r._sujungta_i;

/**
 * The room a room-tool click means → `{nr, how: 'outline' | 'number'}` or null.
 * `point` = {page, x_pct, y_pct} (display fractions); `sutapdinimas` = `_meta.geometrija.sutapdinimas`.
 */
export function roomForToolClick(rooms, point, { sutapdinimas = null } = {}) {
  const page = num(point?.page);
  const x = num(point?.x_pct);
  const y = num(point?.y_pct);
  if (!Array.isArray(rooms) || page == null || x == null || y == null) return null;
  const list = rooms.filter(pickable);
  const inside = list
    .map((r) => ({ r, ring: outlineOn(r, page, sutapdinimas) }))
    .filter(({ ring }) => ring && pointInPolygonPoints(x, y, ring))
    .sort((a, b) => area(a.ring) - area(b.ring));
  if (inside.length) return { nr: String(inside[0].r.nr), how: 'outline' };
  const seats = list
    .map((r) => ({ r, seat: seatOn(r, page, sutapdinimas) }))
    .filter(({ seat }) => seat)
    .map(({ r, seat }) => ({ nr: String(r.nr), d: Math.hypot(seat[0] - x, seat[1] - y) }))
    .sort((a, b) => a.d - b.d);
  if (seats.length) return { nr: seats[0].nr, how: 'number' };
  return null;
}

/** The rooms to offer when the click names none: those without an outline first, then the rest, by number. */
export function pickCandidates(rooms) {
  const list = (Array.isArray(rooms) ? rooms : []).filter(pickable);
  const byNr = (a, b) => String(a.nr).localeCompare(String(b.nr), 'lt', { numeric: true });
  const without = list.filter((r) => !ringOf(r.polygon_pct)).sort(byNr);
  const withOutline = list.filter((r) => ringOf(r.polygon_pct)).sort(byNr);
  return [...without, ...withOutline].map((r) => ({ nr: String(r.nr), name: String(r.pavadinimas || '') }));
}

/**
 * The server says the walls belong to ANOTHER room: `taken` (inside its trusted outline) or `open` with
 * exactly one other room's number inside the face. → that room's nr (to ask once more), else null.
 */
export function retryNrFor(answer, triedNr) {
  if (answer?.status === 'taken' && answer.nr != null && String(answer.nr) !== String(triedNr)) return String(answer.nr);
  if (answer?.status === 'open' && Array.isArray(answer.su) && answer.su.length === 1 && String(answer.su[0]) !== String(triedNr)) {
    return String(answer.su[0]);
  }
  return null;
}

/**
 * The click was inside room `nr`'s own outline, yet the walls give the place to `answer.nr` (`taken`): no wall
 * separates the two — one open space (objektas_h: 04 Virtuvė, 05 Svetainė and 03 Koridorius, divided by lines
 * and a drawn outline). A wall-exact outline does not exist there; say so and where the fix is. Else null.
 */
export function noWallSentence(nr, answer) {
  if (answer?.status !== 'taken' || answer.nr == null || String(answer.nr) === String(nr)) return null;
  return `Patalpos ${nr} nuo patalpos ${answer.nr} sienos neatskiria — kontūro pagal sienas čia nėra. `
    + 'Taisykite kontūrą viršūnėmis („Taisyti kontūrą") arba padalinkite erdvę patalpos lape.';
}

const m2 = (v) => `${ltNumber(v, 2)} m²`;

/** Where a perimeter came from, in his words — for the consequence line. */
function perimeterSource(saltinis) {
  if (saltinis === 'matmenu_eilutes' || saltinis === 'plano_matmenys') return 'pagal brėžinio matmenis';
  if (saltinis === 'user_override' || saltinis === 'manual') return 'jūsų įrašytas';
  if (saltinis === 'sienu_konturas') return 'pagal kontūrą';
  if (saltinis === 'konturo_ivertis' || saltinis === 'atviros_erdves_ivertis') return 'apytikslis';
  return null;
}

/**
 * The proposal's consequence, in two short lines (the label on the drawing):
 *   „04 Virtuvė · kontūras 26,30 m²" / „lentelėje 26,31 m² · sienos 21,40 m pagal brėžinio matmenis".
 * The billing truth is said too: floors and ceilings keep the table's area — the outline is for the walls.
 */
export function proposalLines(room, answer) {
  const geo = answer?.room || {};
  const k = geo._konturas || {};
  const nr = String(room?.nr ?? '');
  const name = String(room?.pavadinimas || '').trim();
  const head = `${nr}${name ? ` ${name}` : ''} · kontūras ${k.plotas_m2 != null ? m2(k.plotas_m2) : '—'}`;
  const parts = [];
  const table = num(room?.plotas_m2);
  if (table != null && table > 0) parts.push(`lentelėje ${m2(table)}`);
  const per = num(geo.perimetras_m);
  if (per != null && per > 0) {
    const src = perimeterSource(geo.perimetras_saltinis);
    parts.push(`sienos ${ltNumber(per, 2)} m${src ? ` ${src}` : ''}`);
  }
  return { title: head, sub: parts.join(' · ') || null };
}

/** The raster fallback's proposal (no vector walls on the sheet): its lines say it is an estimate. */
export function rasterProposalLines(room, ringPct) {
  const nr = String(room?.nr ?? '');
  const name = String(room?.pavadinimas || '').trim();
  return {
    title: `${nr}${name ? ` ${name}` : ''} · kontūras pagal brėžinio vaizdą`,
    sub: ringPct ? 'Šiame lape sienų programa neperskaitė — kontūras apytikslis' : null,
  };
}

/** The holes he cut before („Atimti") that still lie wholly inside the new outline, with their answers. */
export function holesKept(room, ring) {
  const holes = Array.isArray(room?.polygon_holes_pct) ? room.polygon_holes_pct : [];
  const skyles = Array.isArray(room?._konturas?.skyles) ? room._konturas.skyles : [];
  const kept = [];
  holes.forEach((h, i) => {
    const hole = ringOf(h);
    if (hole && ring && hole.every(([x, y]) => pointInPolygonPoints(x, y, ring))) {
      kept.push({ ring: hole, sienos: skyles[i]?.sienos !== false });
    }
  });
  return kept;
}

/** What the commit sends to `outline-set` for a proposal of room `room`. */
export function commitBody(proposal, room) {
  const ring = ringOf(proposal?.ring);
  const holes = holesKept(room, ring);
  return {
    page: Number(proposal?.page),
    polygon_pct: ring,
    ...(holes.length ? { holes: holes.map((h) => h.ring), holes_walls: holes.map((h) => h.sienos) } : {}),
    kaip: 'parodyta',
  };
}

/** Whether a click (display fractions on `page`) lands inside the pending proposal. */
export function insideProposal(proposal, point) {
  const ring = ringOf(proposal?.ring);
  return Boolean(ring && Number(point?.page) === Number(proposal.page)
    && pointInPolygonPoints(Number(point.x_pct), Number(point.y_pct), ring));
}
