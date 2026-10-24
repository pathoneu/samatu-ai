/**
 * scaleChip — what the viewer's scale chip says and offers for the sheet on screen (Pathon v3 wave 1, W1-D, D4;
 * design §4 track E; audit act „Confirm scale" 4 → 1).
 *
 * Confirming a guessed scale took four actions behind a hidden toolbar button (scroll → „Masteliai" →
 * „Patvirtinti" → ✕). The chip sits at the drawing's bottom-left and reads „1:75 — iš plano matmenų (139 skaičiai)"
 * (v4: the words come from the backend's provenance, lib/scaleProvenance); one click opens
 * its card: „Patvirtinti 1:115" (one click), „Patvirtinti visiems N lapams" (the sheets that share the guessed
 * ratio), „Kalibruoti" (the two-click calibration; its dialog offers the nearest standard scale, ticked),
 * „Patikrinti" (the existing check against a known length).
 *
 * One source, the one W0-B unified: the viewer's merged scale map (auto → lane → his own; lib/pageScales) for
 * the state, and lib/scaleOverview's rows for what may be confirmed and which sheets share a ratio. Pure.
 */
import { buildScaleOverview } from './scaleOverview.js';
import { provenanceExplanation, provenancePhrase, provenanceText, scaleProvenanceLine } from './scaleProvenance.js';
import { pageScaleIn } from './pageScales.js';

/**
 * The chip for sheet `page` → {page, state, line, label, text, phrase, sentence, title, canConfirm, group}.
 *   text     what the card's header says: „1:75 — iš plano matmenų (139 skaičiai)" / „mastelio nėra — …";
 *   phrase   the same without the scale (the chip shows the scale in bold beside it);
 *   line     'solid' (read from the drawing or his) · 'dashed' (a proposal) · 'none';
 *   sentence the status line's words (lib/scaleProvenance), the chip's accessible name;
 *   title    why — the plain explanation with the backend's own note (provenanceExplanation);
 *   group    {pages, label} — other unconfirmed sheets with the same lane ratio, this one included, when
 *            there are at least two (else null).
 * `scales` = the viewer's effective map (what it measures with); `project` + `durable` feed the overview;
 * `t` = i18n's translate function (lib/scaleProvenance words every text).
 */
export function scaleChipModel({ page, scales, project = null, durable = null, pageCount = null, t }) {
  const p = Number(page) || 1;
  const scale = pageScaleIn(scales, p);
  const { rows, groups } = buildScaleOverview(project || {}, { pageCount, durable: durable || {} });
  const row = rows.find((r) => r.page === p) || null;
  const desc = row?.desc || { state: 'nenustatytas', line: 'none', label: '', phrase: { key: 'none' }, notes: [], explain: [{ key: 'none' }] };
  const state = row?.state || 'nenustatytas';
  const label = row?.label || '';
  const group = groups.find((g) => g.pages.includes(p)) || null;
  const blankReason = desc.phrase?.params?.reason || '';
  return {
    page: p,
    state,
    line: desc.line,
    label,
    text: provenanceText(desc, t),
    phrase: provenancePhrase(desc, t),
    sentence: scaleProvenanceLine(scale, t, { blankReason }),
    // where it comes from and what that means — the card's own buttons are the „what to do"
    title: provenanceExplanation(desc, t),
    canConfirm: Boolean(row?.canConfirm),
    group: group ? { pages: group.pages, label: group.label } : null,
  };
}
