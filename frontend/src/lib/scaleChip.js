/**
 * scaleChip — what the viewer's scale chip says and offers for the sheet on screen (Pathon v3 wave 1, W1-D, D4;
 * design §4 track E; audit act „Confirm scale" 4 → 1).
 *
 * Confirming a guessed scale took four actions behind a hidden toolbar button (scroll → „Masteliai" →
 * „Patvirtinti" → ✕). The chip sits at the drawing's bottom-left and reads „1:115 · spėjamas"; one click opens
 * its card: „Patvirtinti 1:115" (one click), „Patvirtinti visiems N lapams" (the sheets that share the guessed
 * ratio), „Kalibruoti" (the two-click calibration; its dialog offers the nearest standard scale, ticked),
 * „Patikrinti" (the existing check against a known length).
 *
 * One source, the one W0-B unified: the viewer's merged scale map (auto → lane → his own; lib/pageScales) for
 * the state, and lib/scaleOverview's rows for what may be confirmed and which sheets share a ratio. Pure.
 */
import { buildScaleOverview } from './scaleOverview.js';
import { SCALE_STATE_LT, scaleExplanation, scaleStatusText } from './scaleLabel.js';
import { pageScaleIn } from './pageScales.js';

/**
 * The chip for sheet `page` → {page, state, label, text, sentence, title, canConfirm, group}.
 *   text     what the chip itself says: „1:115 · spėjamas" / „Mastelis nenustatytas";
 *   sentence the status line's words (lib/scaleLabel.scaleStatusText), the card's first line;
 *   title    why — the plain explanation without the status bar's „click here" hints (scaleExplanation);
 *   group    {pages, label} — other unconfirmed sheets with the same guessed ratio, this one included, when
 *            there are at least two (else null).
 * `scales` = the viewer's effective map (what it measures with); `project` + `durable` feed the overview.
 */
export function scaleChipModel({ page, scales, project = null, durable = null, pageCount = null }) {
  const p = Number(page) || 1;
  const scale = pageScaleIn(scales, p);
  const { rows, groups } = buildScaleOverview(project || {}, { pageCount, durable: durable || {} });
  const row = rows.find((r) => r.page === p) || null;
  const state = row?.state || 'nenustatytas';
  const label = row?.label || '';
  const group = groups.find((g) => g.pages.includes(p)) || null;
  return {
    page: p,
    state,
    label,
    text: state === 'nenustatytas' || !label ? 'Mastelis nenustatytas' : `${label} · ${SCALE_STATE_LT[state]}`,
    sentence: scaleStatusText(scale),
    // where it comes from and what that means — the card's own buttons are the „what to do"
    title: scaleExplanation(scale),
    canConfirm: Boolean(row?.canConfirm),
    group: group ? { pages: group.pages, label: group.label } : null,
  };
}
