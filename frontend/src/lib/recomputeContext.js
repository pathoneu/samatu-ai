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
export function buildRecomputeContext(rawData) {
  const d = rawData || {};
  return {
    _door_types: d._door_types,
    detected_symbols_summary: d.detected_symbols_summary,
    _plyteliu_specs: d._plyteliu_specs,
    _symbol_legend: d._symbol_legend,
    bendras_plotas_m2: d.bendras_plotas_m2,
    v9_meta: d.v9_meta,
    _overrides: d._overrides,
    _ceiling_anchor: d._ceiling_anchor,
    _walls_anchor: d._walls_anchor,
    // 2026-09-06: the extraction's own record — the plan-label lane result
    // (`plan_area_lane`: the labels no room claimed, offered as rooms on the
    // general page) and the designer's figures. The recompute response is
    // spread over the project, so a response without them wiped them after
    // the first edit (measured: the „Pridėti kaip patalpą" list vanished).
    _meta: d._meta,
    _autoriaus_kiekiai: d._autoriaus_kiekiai,
  };
}

/** Keys the context carries — exported so a test can pin the contract. */
export const RECOMPUTE_CONTEXT_KEYS = Object.freeze([
  '_door_types', 'detected_symbols_summary', '_plyteliu_specs', '_symbol_legend',
  'bendras_plotas_m2', 'v9_meta', '_overrides', '_ceiling_anchor', '_walls_anchor', '_meta', '_autoriaus_kiekiai',
]);
