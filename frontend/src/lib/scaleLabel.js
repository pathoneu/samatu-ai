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
 *   'user' — his own: two clicks on a distance he knows the length of;
 *   'lane-confirmed' — a lane scale he confirmed (lib/durableScale.confirmedLaneScale, keeps `kilme`).
 * 2026-10-16 (Togal-v2 W6): a lane or area scale is the program's guess and says „Spėjamas" until he confirms
 * it; his own and confirmed ones say „Patvirtintas" (scaleState).
 *
 * 2026-10-06 (contractor walkthrough on objektas_h): „Mastelis: 1:115 (iš brėžinio)" read as a scale written on
 * the drawing; 1:115 is what the dimension strings measure on a sheet printed at another size than drawn. Each
 * state now says where its number comes from — in his words, without the word the vocabulary guard bans for
 * his own calibration. Pure: no React.
 */

import { DRAWING_SCALES, LANE_CONFIRMED } from './durableScale.js';

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

/**
 * The scale's state (Togal-v2 W6, 2026-10-16) — Togal shows a predicted scale and asks a person to confirm it:
 *   'nenustatytas'  no scale in force;
 *   'spejamas'      the program's guess — the lane's dimension strings or the rooms' areas — not yet confirmed;
 *   'patvirtintas'  his: two clicks on a known length, or a lane scale he confirmed (source 'lane-confirmed').
 */
export function scaleState(pageScale) {
  if (!pageScale?.calibrated || !(Number(pageScale.metersPerPointX) > 0)) return 'nenustatytas';
  if (pageScale.source === 'user' || pageScale.source === LANE_CONFIRMED || pageScale.confirmed === true) return 'patvirtintas';
  return 'spejamas';
}

/** The state in his words, for chips and the overview. */
export const SCALE_STATE_LT = Object.freeze({
  nenustatytas: 'nenustatytas',
  spejamas: 'spėjamas',
  patvirtintas: 'patvirtintas',
});

/** Where a lane scale's number comes from, in a few words (the part in brackets). */
function laneOrigin(pageScale) {
  if (pageScale.kilme === 'uzrasytas') return 'užrašytas brėžinyje';
  if (pageScale.kilme === 'ismatuotas') {
    const stated = writtenAs(pageScale);
    return stated ? `išmatuotas pagal matmenis; lape užrašyta ${stated}` : 'išmatuotas pagal matmenis';
  }
  return 'pagal brėžinio matmenis';
}

/**
 * The scale's source in one short phrase — the overview's „Šaltinis" column. Lane and confirmed-lane scales
 * share the lane's wording; his own calibration and the areas say so.
 */
export function scaleSourceText(pageScale) {
  if (scaleState(pageScale) === 'nenustatytas') return 'Nėra';
  const s = pageScale.source;
  if (s === 'plan' || s === LANE_CONFIRMED) {
    const o = laneOrigin(pageScale);
    return o.charAt(0).toUpperCase() + o.slice(1);
  }
  if (s === 'auto') return 'Apytikslis, pagal patalpų plotus';
  if (s === 'user') return 'Jūsų nustatytas pagal žinomą atstumą';
  return 'Nustatytas';
}

/** The status bar's one line: guessed and confirmed scales never read alike. */
export function scaleStatusText(pageScale) {
  if (!pageScale?.calibrated) return 'Mastelis nenustatytas — spustelėkite čia';
  const label = labelOf(pageScale);
  if (!label) return 'Mastelis nustatytas';
  if (pageScale.source === 'plan') return `Spėjamas mastelis ${label} (${laneOrigin(pageScale)})`;
  if (pageScale.source === LANE_CONFIRMED) return `Patvirtintas mastelis ${label} (${laneOrigin(pageScale)})`;
  if (pageScale.source === 'auto') return `Spėjamas mastelis ~${label} (apytikslis, pagal patalpų plotus)`;
  if (pageScale.source === 'user') return `Patvirtintas mastelis ${label} (jūsų nustatytas)`;
  return `Mastelis ${label}`;
}

const CONFIRM_HINT = 'Tai programos spėjimas — patvirtinkite jį skydelyje „Masteliai" arba patikrinkite žinomu matmeniu.';

/**
 * Its tooltip — one plain explanation per state (the line itself already says the source; this says what it
 * means for his measurements).
 */
export function scaleStatusTitle(pageScale) {
  if (!pageScale?.calibrated) {
    return 'Mastelis dar nenustatytas — matavimai bus be metrų. Spustelėkite ir pažymėkite atkarpą, kurios tikrą ilgį žinote.';
  }
  const label = labelOf(pageScale);
  const lane = pageScale.source === 'plan' || pageScale.source === LANE_CONFIRMED;
  if (lane) {
    let why;
    if (pageScale.kilme === 'uzrasytas') {
      why = `Mastelis ${label} užrašytas brėžinio lape, ir plane užrašyti matmenys jį patvirtina.`;
    } else if (pageScale.kilme === 'ismatuotas') {
      const stated = writtenAs(pageScale);
      if (stated) {
        why = `Lape užrašyta ${stated}, bet plane užrašyti matmenys rodo ${label} — lapas atspausdintas kitu dydžiu, `
          + 'nei braižytas. Matuojama pagal matmenis.';
      } else {
        const odd = !DRAWING_SCALES.includes(ratioOf(pageScale))
          ? ` ${label} nėra įprastas braižymo mastelis — lapas, matyt, atspausdintas kitu dydžiu, nei braižytas.`
          : '';
        why = `Mastelis išmatuotas pagal plane užrašytus matmenis: jų skaičiai palyginti su nubrėžtų linijų ilgiais.${odd}`;
      }
    } else {
      why = 'Mastelis nustatytas pagal plane užrašytus matmenis.';
    }
    if (pageScale.source === LANE_CONFIRMED) return `${why} Jūs jį patvirtinote. ${CLICK_TO_SET}`;
    return `${why} ${CONFIRM_HINT} ${CLICK_TO_SET}`;
  }
  if (pageScale.source === 'auto') {
    return 'Mastelis apskaičiuotas iš patalpų plotų eksplikacijoje — todėl apytikslis (~). Norėdami tikslesnio, spustelėkite ir nustatykite mastelį pagal žinomą atstumą.';
  }
  if (pageScale.source === 'user') {
    return 'Mastelį nustatėte patys pagal atstumą, kurio tikrą ilgį žinote. Spustelėkite, jei norite nustatyti iš naujo.';
  }
  return `Mastelis ${label}. ${CLICK_TO_SET}`;
}
