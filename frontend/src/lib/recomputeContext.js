/**
 * buildRecomputeContext — the reader context every recompute call must carry.
 *
 * Both recompute endpoints (`/api/recompute-quantities` for Prielaidos edits,
 * `/recompute-interior` for room/polygon edits) rebuild the darbų sąrašas from
 * the rooms, and the builder reads reader outputs that live on the project
 * blob rather than on the rooms: door types, symbol counts, tile specs, the
 * eksplikacijos „Iš viso" the ceiling is billed off. A caller that forgets
 * one of them gets a quieter sąmata for no reason the user can see (the
 * 2026-06-17 door/fixture loss; the 2026-09-02 un-anchored Lubų row). One
 * helper, two callers, nothing to drift.
 */
import { measuredContributions } from './measuredRows.js';

export function buildRecomputeContext(rawData) {
  const d = rawData || {};
  const matavimai = measuredContributions(d);
  return {
    _door_types: d._door_types,
    detected_symbols_summary: d.detected_symbols_summary,
    _plyteliu_specs: d._plyteliu_specs,
    _symbol_legend: d._symbol_legend,
    // 2026-09-23: the drawing's door schedule (extractor/door_schedule) — the frameless-door assumption and
    // the door list's reconciliation with the table are settled from it on every recompute
    _duru_ziniarastis: d._duru_ziniarastis,
    // 2026-09-24: the symbols counted from the drawing's own paths (extractor/vector_symbols) — the diffuser
    // rows take this count on every rebuild
    _vector_symbols: d._vector_symbols,
    bendras_plotas_m2: d.bendras_plotas_m2,
    v9_meta: d.v9_meta,
    _overrides: d._overrides,
    _ceiling_anchor: d._ceiling_anchor,
    _walls_anchor: d._walls_anchor,
    _floor_anchors: d._floor_anchors,
    // 2026-09-06: the extraction's own record — the plan-label lane result
    // (`plan_area_lane`: the labels no room claimed, offered as rooms on the
    // general page) and the designer's figures. The recompute response is
    // spread over the project, so a response without them wiped them after
    // the first edit (measured: the „Pridėti kaip patalpą" list vanished).
    _meta: d._meta,
    _autoriaus_kiekiai: d._autoriaus_kiekiai,
    // Pathon v3 W4-A: what he measured on rows (lib/measuredRows.js) — the rebuilt rows come back carrying their
    // „matavimas" lines (backend api/measured_rows.py). Absent when nothing is linked: the request is unchanged.
    matavimai: matavimai.length ? matavimai : undefined,
  };
}

/** Keys the context carries — exported so a test can pin the contract. */
export const RECOMPUTE_CONTEXT_KEYS = Object.freeze([
  '_door_types', 'detected_symbols_summary', '_plyteliu_specs', '_symbol_legend', '_duru_ziniarastis',
  '_vector_symbols', 'bendras_plotas_m2', 'v9_meta', '_overrides', '_ceiling_anchor', '_walls_anchor', '_floor_anchors', '_meta', '_autoriaus_kiekiai',
  'matavimai',
]);
