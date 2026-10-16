/**
 * scaleGate — may a tool that needs metres run on this sheet? (Togal-v2 W6, Togal §2.5: the green button reads
 * „Set scale" and is disabled until the page has one.)
 *
 * Pathon does NOT block: measuring and counting work today without a scale, and a gate must never take that
 * away. Callers show `reason` as a soft chip; the detection button (W3, „Perskaityti lapą") is meant to call
 * `scaleGateFor(project, page)` and, when `ok` is false, offer „Nustatyti mastelį" next to its run button
 * rather than refuse the run (the lane measures the scale itself as its first stage).
 *
 * `ok` false only when no scale at all is in force; a guessed (spėjamas) scale is in force — `state` says which.
 */
import { effectivePageScales, pageScaleIn } from './pageScales.js';
import { scaleState } from './scaleLabel.js';

export const SCALE_UNSET_REASON = 'Mastelis nenustatytas — matavimai bus be metrų';

/** Gate from a PageScale already merged (the viewer has its live map). */
export function scaleGateFromScale(scale) {
  const state = scaleState(scale);
  if (state === 'nenustatytas') return { ok: false, reason: SCALE_UNSET_REASON, scale: null, state };
  return { ok: true, reason: null, scale, state };
}

/**
 * `{ok, reason, scale, state}` for one sheet of a project. `durable` overrides the stored map (live viewer
 * state), the same way effectivePageScales takes it.
 */
export function scaleGateFor(project, page, durable) {
  const scales = durable === undefined ? effectivePageScales(project) : effectivePageScales(project, durable);
  return scaleGateFromScale(pageScaleIn(scales, page));
}
