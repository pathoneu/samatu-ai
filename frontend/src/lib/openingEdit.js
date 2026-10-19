/**
 * openingEdit — a door or window edited on the drawing (Pathon v3 W5-A A9 [D-openings], A2 „Iškirpti angą").
 *
 * The walls layer draws every opening the lane read in a room's walls (`room._angos_sienose = {page, angos:
 * [{line_pct, plotis_m, i, nupiesta?}]}`). The room's doors and windows the quantities are built from are
 * `room.elementai`; an entry stands in an opening when its `_anga_ks` lists that opening's index. A click on
 * an opening mark opens a pop-up (width, kind: langas / durys / praėjimas); saving rewrites that one entry the
 * way the room sheet's opening edit does (lib/roomSheet: `_dydis_user`, and the host's openingsPatch marks the
 * room's openings as his — USER_OPENINGS_KEY on the server keeps them through every recompute).
 *
 * Nothing is invented: the width is the one he typed or the one the walls show; a new entry's height is the
 * standard the engine already assumes for that kind (lib/roomSheet STANDARD_OPENINGS). Pure.
 */
import { STANDARD_OPENINGS, addOpening } from './roomSheet.js';
import { roomPageOf } from './roomZones.js';

export const OPENING_KINDS = Object.freeze([
  { id: 'langas', label: 'Langas' },
  { id: 'durys', label: 'Durys' },
  { id: 'praejimas', label: 'Praėjimas (be durų)' },
]);

const TIPAS = { langas: 'langas', durys: 'duris' };

/** Every opening mark on `page`: {nr, k, i, line: [[x,y],[x,y]], plotisM, nupiesta}. */
export function openingsOnPage(rooms, page) {
  const out = [];
  for (const r of rooms || []) {
    const a = r?._angos_sienose;
    if (!a || Number(a.page) !== Number(page) || !Array.isArray(a.angos)) continue;
    a.angos.forEach((g, k) => {
      if (!Array.isArray(g?.line_pct) || g.line_pct.length !== 2) return;
      out.push({ nr: String(r.nr), k, i: g.i != null ? String(g.i) : null, line: g.line_pct, plotisM: Number(g.plotis_m) || null, nupiesta: g.nupiesta || null });
    });
  }
  return out;
}

function segDist([px, py], [[ax, ay], [bx, by]], sx = 1, sy = 1) {
  const dx = (bx - ax) * sx; const dy = (by - ay) * sy;
  const len2 = dx * dx + dy * dy;
  const t = len2 ? Math.min(1, Math.max(0, (((px - ax) * sx) * dx + ((py - ay) * sy) * dy) / len2)) : 0;
  return Math.hypot((px - ax) * sx - t * dx, (py - ay) * sy - t * dy);
}

/**
 * The opening mark under a click (`pt` display fractions), within `tolPx` screen px on a sheet drawn `w`×`h` px.
 * The focused room's mark wins when two rooms read the same opening (both sides of one door).
 */
export function openingAt(rooms, page, pt, { tolPx = 8, w = 1000, h = 1000, preferNr = null, nr = null } = {}) {
  let best = null;
  for (const o of openingsOnPage(rooms, page)) {
    if (nr != null && o.nr !== String(nr)) continue;
    const d = segDist(pt, o.line, w, h);
    if (d > tolPx) continue;
    const score = d - (preferNr != null && o.nr === String(preferNr) ? 0.5 : 0);
    if (!best || score < best.score) best = { ...o, score };
  }
  if (!best) return null;
  const { score: _s, ...o } = best;
  return o;
}

/** The index of the `elementai` entry standing in opening `k`, or -1. */
export function linkedEntry(elementai, k) {
  return (elementai || []).findIndex((el) => Array.isArray(el?._anga_ks) && el._anga_ks.map(Number).includes(Number(k)));
}

/** What the pop-up starts from: {kind, plotisMm, aukstisMm, linked} for opening `o` of `room`. */
export function openingState(room, o) {
  const idx = linkedEntry(room?.elementai, o.k);
  const el = idx >= 0 ? room.elementai[idx] : null;
  // no entry stands in it: the program counts no door or window here — a passage, whatever the drawing shows
  const kind = el ? (el.tipas === 'langas' ? 'langas' : 'durys') : 'praejimas';
  const plotisMm = el && Number(el.plotis_mm) > 0 ? Math.round(Number(el.plotis_mm)) : (o.plotisM ? Math.round(o.plotisM * 1000) : null);
  return { kind, plotisMm, aukstisMm: el ? Number(el.aukstis_mm) || null : null, linked: idx >= 0 };
}

/**
 * `elementai` with opening `o` set to {kind, plotisMm} — or null when nothing changes. An entry that stands
 * in several openings (`kiekis` > 1) gives this one up and a new entry stands in it alone.
 */
export function applyOpeningEdit(elementai, o, { kind, plotisMm }) {
  const list = Array.isArray(elementai) ? elementai : [];
  const idx = linkedEntry(list, o.k);
  const w = Math.round(Number(plotisMm));
  if (kind !== 'praejimas' && !(w > 0)) return null;
  const fresh = (base = null) => ({
    tipas: TIPAS[kind],
    kiekis: 1,
    plotis_mm: w,
    aukstis_mm: base && base.tipas === TIPAS[kind] && Number(base.aukstis_mm) > 0 ? Number(base.aukstis_mm) : STANDARD_OPENINGS[TIPAS[kind]].aukstis_mm,
    _anga_ks: [o.k],
    ...(o.i ? { _is_sienu_angos: o.i } : {}),
    _dydis_user: true,
  });
  if (idx < 0) {
    if (kind === 'praejimas') return null;
    return [...list, fresh()];
  }
  const el = list[idx];
  const ks = el._anga_ks.map(Number);
  const shared = ks.length > 1 || (Number(el.kiekis) || 1) > 1;
  if (!shared) {
    if (kind === 'praejimas') return list.filter((_, n) => n !== idx);
    const same = el.tipas === TIPAS[kind] && Math.round(Number(el.plotis_mm)) === w;
    if (same) return null;
    return list.map((x, n) => (n === idx ? { ...x, ...fresh(x), kiekis: Number(x.kiekis) || 1, _anga_ks: x._anga_ks, _schedule_anchored: false } : x));
  }
  const rest = { ...el, kiekis: Math.max(0, (Number(el.kiekis) || ks.length) - 1), _anga_ks: el._anga_ks.filter((k) => Number(k) !== Number(o.k)) };
  const next = list.map((x, n) => (n === idx ? rest : x)).filter((x) => (Number(x.kiekis) || 0) > 0);
  return kind === 'praejimas' ? next : [...next, fresh(el)];
}

/**
 * „Iškirpti angą" on a room's outline edge (A2): the opening the walls show nearest that place on this room —
 * its kind and width — or a standard door when the walls show none there. → {opening, from: 'walls' | 'standard'}.
 */
export function openingForEdge(room, page, pt, opts = {}) {
  const o = room && roomPageOf(room) != null ? openingAt([room], page, pt, { ...opts, tolPx: opts.tolPx ?? 30 }) : null;
  if (o && o.plotisM) {
    const kind = o.nupiesta === 'langas' ? 'langas' : 'durys';
    return { from: 'walls', o, kind, plotisMm: Math.round(o.plotisM * 1000) };
  }
  return { from: 'standard', o: null, kind: 'durys', plotisMm: STANDARD_OPENINGS.duris.plotis_mm };
}

/** `elementai` with the edge's opening added (A2): into the read opening's entry, or a standard door. */
export function addEdgeOpening(elementai, choice) {
  if (choice.o) return applyOpeningEdit(elementai, choice.o, { kind: choice.kind, plotisMm: choice.plotisMm });
  return addOpening(elementai, STANDARD_OPENINGS.duris);
}

/** „Durys 0,90 m" — the opening as the pop-up and the toast say it. */
export function openingText(kind, plotisMm) {
  const word = kind === 'langas' ? 'Langas' : kind === 'durys' ? 'Durys' : 'Praėjimas';
  if (!(Number(plotisMm) > 0)) return word;
  return `${word} ${(Number(plotisMm) / 1000).toFixed(2).replace('.', ',')} m`;
}
