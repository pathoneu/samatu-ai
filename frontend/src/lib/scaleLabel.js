/**
 * scaleLabel — what the viewer's status bar says about the current page's scale, and where it comes from.
 *
 * A PageScale stores metres of reality per PDF point; 1 pt = 1/72 inch of paper, so the 1:N ratio is
 * mpp / (0.0254 / 72). Sources (`source`):
 *   'plan' — the drawing's own dimension strings (lib/durableScale.laneScalesOf), with `kilme`:
 *            'uzrasytas'  written on the sheet, and the dimensions agree;
 *            'ismatuotas' measured from the dimensions (`uzrasyta`: the scale the sheet writes, if another);
 *            'matmenys'   from the dimensions, written or measured not known;
 *   'auto' — derived from the rooms' areas in the eksplikacija (approximate);
 *   'user' — his own: two clicks on a distance he knows the length of.
 *
 * 2026-10-06 (contractor walkthrough on objektas_h): „Mastelis: 1:115 (iš brėžinio)" read as a scale written on
 * the drawing; 1:115 is what the dimension strings measure on a sheet printed at another size than drawn. Each
 * state now says where its number comes from — in his words, without the word the vocabulary guard bans for
 * his own calibration. Pure: no React.
 */

import { DRAWING_SCALES } from './durableScale.js';

const CLICK_TO_SET = 'Spustelėkite, jei norite nustatyti mastelį pagal kitą žinomą atstumą.';

function ratioOf(pageScale) {
  const mpp = pageScale?.metersPerPointX || 0;
  return mpp > 0 ? Math.round((mpp * 72) / 0.0254) : 0;
}

function labelOf(pageScale) {
  if (pageScale?.label) return pageScale.label;
  const ratio = ratioOf(pageScale);
  return ratio > 0 ? `1:${ratio}` : '';
}

const writtenAs = (pageScale) => (pageScale?.uzrasyta || []).filter((n) => Number(n) > 0).map((n) => `1:${n}`).join(', ');

/** The status bar's one line. */
export function scaleStatusText(pageScale) {
  if (!pageScale?.calibrated) return 'Mastelis nenustatytas — spustelėkite čia';
  const label = labelOf(pageScale);
  if (!label) return 'Mastelis nustatytas';
  if (pageScale.source === 'plan') {
    if (pageScale.kilme === 'uzrasytas') return `Mastelis ${label} (užrašytas brėžinyje)`;
    if (pageScale.kilme === 'ismatuotas') {
      const stated = writtenAs(pageScale);
      return stated
        ? `Mastelis ${label} (išmatuotas pagal matmenis; lape užrašyta ${stated})`
        : `Mastelis ${label} (išmatuotas pagal matmenis)`;
    }
    return `Mastelis ${label} (pagal brėžinio matmenis)`;
  }
  if (pageScale.source === 'auto') return `Mastelis ~${label} (apytikslis, pagal patalpų plotus)`;
  if (pageScale.source === 'user') return `Mastelis ${label} (jūsų nustatytas)`;
  return `Mastelis ${label}`;
}

/**
 * Its tooltip — one plain explanation per state (the line itself already says the source; this says what it
 * means for his measurements).
 */
export function scaleStatusTitle(pageScale) {
  if (!pageScale?.calibrated) {
    return 'Mastelis dar nenustatytas — matavimai bus be metrų. Spustelėkite ir pažymėkite atkarpą, kurios tikrą ilgį žinote.';
  }
  const label = labelOf(pageScale);
  if (pageScale.source === 'plan') {
    if (pageScale.kilme === 'uzrasytas') {
      return `Mastelis ${label} užrašytas brėžinio lape, ir plane užrašyti matmenys jį patvirtina — matavimai tikslūs. ${CLICK_TO_SET}`;
    }
    if (pageScale.kilme === 'ismatuotas') {
      const stated = writtenAs(pageScale);
      if (stated) {
        return `Lape užrašyta ${stated}, bet plane užrašyti matmenys rodo ${label} — lapas atspausdintas kitu dydžiu, `
          + `nei braižytas. Matuojama pagal matmenis, todėl matavimai teisingi. ${CLICK_TO_SET}`;
      }
      const odd = !DRAWING_SCALES.includes(ratioOf(pageScale))
        ? ` ${label} nėra įprastas braižymo mastelis — lapas, matyt, atspausdintas kitu dydžiu, nei braižytas; matavimai vis tiek teisingi.`
        : '';
      return `Mastelis išmatuotas pagal plane užrašytus matmenis: jų skaičiai palyginti su nubrėžtų linijų ilgiais.${odd} ${CLICK_TO_SET}`;
    }
    return `Mastelis nustatytas pagal plane užrašytus matmenis — matavimai tikslūs. ${CLICK_TO_SET}`;
  }
  if (pageScale.source === 'auto') {
    return 'Mastelis apskaičiuotas iš patalpų plotų eksplikacijoje — todėl apytikslis (~). Norėdami tikslesnio, spustelėkite ir nustatykite mastelį pagal žinomą atstumą.';
  }
  if (pageScale.source === 'user') {
    return 'Mastelį nustatėte patys pagal atstumą, kurio tikrą ilgį žinote. Spustelėkite, jei norite nustatyti iš naujo.';
  }
  return `Mastelis ${label}. ${CLICK_TO_SET}`;
}
