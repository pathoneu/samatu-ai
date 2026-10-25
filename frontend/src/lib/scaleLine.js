/**
 * scaleLine — the „Skaičius" tool's half that needs no screen (Phase 4, 2026-10-25; plan 2026-10-24 §3.4 / §3.6).
 *
 * The person drags a line over a written dimension („4280"); the backend reads the string under the line
 * (`POST /api/projects/{id}/geometry/scale-line`, backend/api/geometry.py) and answers either
 *   {status: 'ok', page, scale: {m_per_pt, mastelis, source: 'user_line', source_text, confidence, …}}  or
 *   {status: 'blank', page, reason}  — a plain Lithuanian sentence saying what to check.
 * This module turns the drag into the request body and the answer into a PageScale the viewer's chip words through
 * lib/scaleProvenance („1:50 — jūsų nubrėžta linija ant „4280“"). Pure; the network is lib/scaleLineApi.js.
 *
 * Spaces: the drag arrives as UNROTATED mediabox PDF points (the viewer's adapter); the backend's default frame is
 * "display" — points from the sheet's top-left with /Rotate applied — so the points go through the same rotation the
 * scale check uses (lib/scaleCheck.js).
 */
import { normalizeRotation, rotatePctPoint } from './viewerEngine/pageRotation.js';
import { METERS_PER_POINT_AT_1_TO_1 } from './durableScale.js';

/** A drag shorter than this (screen px) is a click, not a line. */
export const MIN_DRAG_PX = 8;

/** Mediabox point → display-frame point (points from the top-left, /Rotate applied). */
export function toDisplayPoint(p, pageSize, rotation = 0) {
  const w = Number(pageSize?.width) || 0;
  const h = Number(pageSize?.height) || 0;
  if (!(w > 0) || !(h > 0)) return null;
  const r = normalizeRotation(rotation);
  const [fx, fy] = rotatePctPoint(Number(p.x) / w, Number(p.y) / h, r);
  const dw = r === 90 || r === 270 ? h : w;
  const dh = r === 90 || r === 270 ? w : h;
  return [Math.round(fx * dw * 100) / 100, Math.round(fy * dh * 100) / 100];
}

/** `{page, p1, p2}` for the request, or null when the sheet's size is not known yet. */
export function scaleLineBody({ page, a, b, pageSize, rotation = 0 }) {
  const p1 = toDisplayPoint(a, pageSize, rotation);
  const p2 = toDisplayPoint(b, pageSize, rotation);
  if (!p1 || !p2) return null;
  return { page: Number(page), p1, p2 };
}

/**
 * The backend's answer as the viewer needs it:
 *   {ok: true, page, pageScale, text}  — pageScale = a lane-shaped PageScale carrying the provenance record, so
 *                                         describeScale words it; `text` = the string the line lay over;
 *   {ok: false, page, reason}          — `reason` is the backend's own sentence (never empty).
 */
export function scaleLineOutcome(resp) {
  const page = Number(resp?.page) || 0;
  const sc = resp?.scale;
  const mpp = Number(sc?.m_per_pt);
  if (resp?.status === 'ok' && mpp > 0) {
    const text = String(sc.source_text || '').trim();
    const ratio = Math.round(mpp / METERS_PER_POINT_AT_1_TO_1);
    return {
      ok: true,
      page,
      text,
      pageScale: {
        metersPerPointX: mpp, metersPerPointY: mpp, calibrated: true, source: 'plan', label: `1:${ratio}`,
        kilme: 'ismatuotas', uzrasyta: [],
        provenance: { saltinis: 'user_line', patikimumas: 'high', ...(text ? { tekstas: text } : {}) },
      },
    };
  }
  const reason = typeof resp?.reason === 'string' && resp.reason.trim()
    ? resp.reason.trim()
    : 'Linijos nepavyko perskaityti — nubrėžkite ją išilgai užrašyto matmens.';
  return { ok: false, page, reason };
}
