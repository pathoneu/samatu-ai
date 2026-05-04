// frontend/src/lib/gestureApi.js
/**
 * Sprint 2: gesture API client wrappers.
 *
 * Each gesture function takes plain JS objects and POSTs the
 * snake_case body backend expects. AbortSignal is plumbed through so
 * rapid sequential gestures cancel prior calls (see abortRegistry.js).
 */
const API_BASE = import.meta.env?.VITE_API_BASE || '';

async function postJson(path, body, signal) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail ?? err;
    const message = typeof detail === 'string' ? detail : detail.user_message || `HTTP ${res.status}`;
    const wrapped = new Error(message);
    wrapped.envelope = detail;
    wrapped.status = res.status;
    throw wrapped;
  }
  return res.json();
}

export function visionFill({ projectId, pageIdx, clickXyPct, viewportState, signal }) {
  return postJson('/api/vision-fill', {
    project_id: projectId,
    page_idx: pageIdx,
    click_xy_pct: clickXyPct,
    viewport_state: viewportState ?? {},
  }, signal);
}

export function lassoRerun({ projectId, pageIdx, lassoPolygonPct, signal }) {
  return postJson('/api/lasso-rerun', {
    project_id: projectId,
    page_idx: pageIdx,
    lasso_polygon_pct: lassoPolygonPct,
  }, signal);
}

function recompute({ rooms, pozicijos, edits, currentAssumptions, signal }) {
  return postJson('/api/recompute-quantities', {
    rooms, pozicijos, edits, current_assumptions: currentAssumptions ?? {},
  }, signal);
}

export function addSymbol({ rooms, pozicijos, targetPozicijaId, pointXyPct, currentAssumptions, signal }) {
  return recompute({
    rooms, pozicijos, currentAssumptions, signal,
    edits: [{ field: 'add_symbol', target_pozicija_id: targetPozicijaId,
              delta: 1, point_xy_pct: pointXyPct }],
  });
}

export function removeSymbol({ rooms, pozicijos, targetPozicijaId, currentAssumptions, signal }) {
  return recompute({
    rooms, pozicijos, currentAssumptions, signal,
    edits: [{ field: 'remove_symbol', target_pozicija_id: targetPozicijaId, delta: 1 }],
  });
}

export function overrideQuantity({ rooms, pozicijos, targetPozicijaId, newValue, currentAssumptions, signal }) {
  return recompute({
    rooms, pozicijos, currentAssumptions, signal,
    edits: [{ field: 'override_pozicija', target_pozicija_id: targetPozicijaId,
              new_value: newValue }],
  });
}

export function colorZone({ rooms, pozicijos, targetRoomId, colorRgb, polygonsPct, currentAssumptions, signal }) {
  return recompute({
    rooms, pozicijos, currentAssumptions, signal,
    edits: [{ field: 'color_zone', target_room_id: targetRoomId,
              color_rgb: colorRgb, polygons_pct: polygonsPct }],
  });
}
