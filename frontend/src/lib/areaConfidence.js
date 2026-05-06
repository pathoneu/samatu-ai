/**
 * areaConfidence — classify per-room area trust based on agreeing sources.
 *
 * Coordinate convention: rooms come from projectStore.patalpos (FLAT shape;
 * NOT proj.data.patalpos). Inputs may include any of:
 *   - plotas_m2 / plotas_source: 'eksplikacija' | 'vision' | 'manual_polygon'
 *   - polygon_pdf + polygon_source: 'manual'   (Phase C-1 manual trace)
 *   - _polygon_area_m2 (optional, computed when polygon committed)
 *   - user_verified_at (ISO timestamp; user clicked ✓ patvirtinta)
 *
 * Returns:
 *   { confidence: 'high'|'medium'|'low'|'unknown',
 *     primarySource: string,
 *     agreeingSources: string[],
 *     userVerified: boolean,
 *     disagreement: boolean,
 *     sources: [{ type, value, label }] }
 *
 * Confidence rules:
 *   - 'unknown' if plotas_m2 is null/undefined
 *   - 'high' if userVerified, OR if ≥2 sources agree within ±2%
 *   - 'low' if ≥2 sources disagree by >5%
 *   - 'medium' otherwise (single source, or sources within 2-5%)
 */

export const AREA_HIGH_AGREEMENT_PCT = 0.02;
export const AREA_AGREEMENT_TOLERANCE_PCT = 0.05;

const SOURCE_LABEL_LT = {
  eksplikacija: 'iš eksplikacijos',
  manual_polygon: 'manualu',
  vision: 'iš AI',
  dimension: 'iš dimensijos',
};

export function computeAreaConfidence(room) {
  if (!room || room.plotas_m2 == null) {
    return {
      confidence: 'unknown',
      primarySource: null,
      agreeingSources: [],
      userVerified: false,
      disagreement: false,
      sources: [],
    };
  }

  const sources = collectSources(room);
  const userVerified = !!room.user_verified_at;

  if (sources.length === 0) {
    return {
      confidence: 'unknown',
      primarySource: null,
      agreeingSources: [],
      userVerified,
      disagreement: false,
      sources: [],
    };
  }

  const primarySource = sources[0].type;

  if (sources.length === 1) {
    // Single-source confidence by source type. Eksplikacija and manual_polygon
    // are deterministic / user-set — they ARE the source of truth, so a single
    // hit is high-confidence. Vision is the only source that's unreliable
    // alone and warrants a 🔴 prompt to verify.
    //   - vision alone → 'low' (Vision pixel-coords are unreliable)
    //   - eksplikacija alone → 'high' (deterministic pdfplumber extraction)
    //   - manual_polygon alone → 'high' (user explicitly traced)
    //   - dimension alone → 'medium' (depends on Vision OCR quality)
    //   - userVerified always reaches 'high'
    let singleConfidence;
    if (userVerified) singleConfidence = 'high';
    else if (primarySource === 'vision') singleConfidence = 'low';
    else if (primarySource === 'eksplikacija' || primarySource === 'manual_polygon') singleConfidence = 'high';
    else singleConfidence = 'medium';
    return {
      confidence: singleConfidence,
      primarySource,
      agreeingSources: [primarySource],
      userVerified,
      disagreement: false,
      sources,
    };
  }

  // 2+ sources — check agreement
  const values = sources.map((s) => s.value).filter((v) => v != null);
  const { agree, disagree } = agreementOf(values);

  if (disagree) {
    return {
      confidence: 'low',
      primarySource,
      agreeingSources: agree.map((idx) => sources[idx].type),
      userVerified,
      disagreement: true,
      sources,
    };
  }

  // All within tolerance
  return {
    confidence: 'high',
    primarySource,
    agreeingSources: sources.map((s) => s.type),
    userVerified,
    disagreement: false,
    sources,
  };
}

/**
 * Effective plotas_source for UI elements that need it directly (e.g. the
 * ProvenanceChip). Handles the Phase C-2 backfill (legacy projects with
 * plotas_m2 but no plotas_source flag → treat as 'eksplikacija') so chips
 * appear correctly on pre-2026-05-02 projects too.
 */
export function inferPlotasSource(room) {
  if (!room || room.plotas_m2 == null) return null;
  // 2026-05-06: plotas_saltinis is authoritative — it overrides plotas_source
  // because the old backend fallback wrote plotas_source="vision" even for
  // eksplikacija rooms. saltinis comes from the deterministic eksplikacija
  // reader and never lies.
  const saltinis = (room.plotas_saltinis || '').trim();
  if (saltinis === 'eksplikacija') return 'eksplikacija';
  if (room.plotas_source) return room.plotas_source;
  if (
    Array.isArray(room.polygon_pdf) &&
    room.polygon_pdf.length >= 3 &&
    room.polygon_source === 'manual'
  ) {
    return 'manual_polygon';
  }
  if (saltinis === 'wall_dim_calc' || saltinis === 'vision') return 'vision';
  return 'eksplikacija';
}

function collectSources(room) {
  const out = [];
  // 2026-05-06: plotas_saltinis (LT, set by deterministic eksplikacija reader)
  // is authoritative — it overrides legacy plotas_source="vision" that the
  // old backend fallback wrote even for eksplikacija rooms. This fixes the
  // cached-project 🔴 neaišku bug visible in user screenshot.
  const saltinisIsEksplikacija =
    (room.plotas_saltinis || '').trim() === 'eksplikacija';
  if ((room.plotas_source === 'eksplikacija' || saltinisIsEksplikacija) && room.plotas_m2 != null) {
    out.push({ type: 'eksplikacija', value: room.plotas_m2, label: SOURCE_LABEL_LT.eksplikacija });
  }
  // A room counts as having a manual_polygon source if EITHER
  //   (a) it has polygon_pdf + polygon_source==='manual' (Phase C-1 trace),
  //   (b) plotas_source is explicitly 'manual_polygon' (committed source flag).
  const hasPolygonTrace =
    Array.isArray(room.polygon_pdf) &&
    room.polygon_pdf.length >= 3 &&
    room.polygon_source === 'manual';
  const hasManualSourceFlag = room.plotas_source === 'manual_polygon' && room.plotas_m2 != null;
  if (hasPolygonTrace || hasManualSourceFlag) {
    const value = room._polygon_area_m2 != null ? room._polygon_area_m2 : room.plotas_m2;
    out.push({ type: 'manual_polygon', value, label: SOURCE_LABEL_LT.manual_polygon });
  }
  // Vision source — only when plotas_saltinis ALSO does not say eksplikacija
  // (saltinis is the deterministic truth; legacy plotas_source may lie).
  if (room.plotas_source === 'vision' && room.plotas_m2 != null && !saltinisIsEksplikacija) {
    out.push({ type: 'vision', value: room.plotas_m2, label: SOURCE_LABEL_LT.vision });
  }
  // Phase C-2 backfill: projects extracted before the plotas_source audit
  // landed have plotas_m2 but no plotas_source flag. pdfplumber eksplikacija HIT
  // is the dominant historical path; treat missing-source-with-area as legacy
  // eksplikacija. New extractions get the explicit flag from the backend.
  if (out.length === 0 && room.plotas_m2 != null && !room.plotas_source) {
    out.push({ type: 'eksplikacija', value: room.plotas_m2, label: SOURCE_LABEL_LT.eksplikacija });
  }
  return out;
}

/**
 * Given an array of numeric values, return whether they all agree within ±5%
 * of the mean. Returns { agree: indices[], disagree: bool }.
 */
export function agreementOf(values) {
  if (!values || values.length === 0) return { agree: [], disagree: false };
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const indices = [];
  let disagree = false;
  values.forEach((v, i) => {
    const pct = Math.abs(v - mean) / mean;
    if (pct <= AREA_AGREEMENT_TOLERANCE_PCT) indices.push(i);
    else disagree = true;
  });
  return { agree: indices, disagree };
}
