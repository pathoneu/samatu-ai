/**
 * scaleProvenance — the ONE place a sheet's scale is put into words (v4, 2026-10-24).
 *
 * The backend (backend/geometry/scale.py, `lane_record`) stores where each sheet's scale comes from in
 * `_meta.geometrija.masteliai[page]` beside `m_per_pt` / `mastelis`:
 *   saltinis     user_line · dimension_lines · dimension_walls · stated · sibling · blank
 *   patikimumas  high · medium · low
 *   tekstas      its own short note („139 matmenų eilutės ant matmenų linijų", „M 1:75 (patvirtina 4 lapo
 *                matmenys)", „M 1:50 (užrašytas, nepatikrintas)", „…; sutampa su užrašytu M 1:50")
 *   is_lapo      the sheet the measurement was made on (a sibling, or the sheet that confirms a written scale)
 *   pastaba      a plain LT note (a written scale the dimensions contradict, centimetres…)
 * and `_meta.geometrija.masteliai_tusti[page]` = why an asked sheet has none.
 *
 * Before this file the viewer built the wording from older keys (`kilme`, guessed from how exactly the metres
 * per point matched a drawing scale) and called every lane scale „Spėjamas" — on objektas_i a scale measured
 * from 139 dimension strings read „Spėjamas mastelis 1:75 (užrašytas brėžinyje)". Now:
 *   state 'nuskaitytas'  read from the drawing (backend source with high / medium confidence) — solid line;
 *   state 'spejamas'     ONLY when the backend says low confidence, or there is no backend source at all (old
 *                        blobs, the rooms' areas) — dashed line;
 *   state 'patvirtintas' his own, or a lane scale he confirmed — solid line;
 *   state 'nenustatytas' none — the reason from `masteliai_tusti` when there is one.
 *
 * Pure. Words come from i18n (`project.scaleProvenance.*`): every function that returns text takes `t`
 * (react's useTranslation().t, or any function with the same contract).
 */
import { DRAWING_SCALES, LANE_CONFIRMED } from './durableScale.js';

const NS = 'project.scaleProvenance';
export const BACKEND_SOURCES = Object.freeze(['user_line', 'dimension_lines', 'dimension_walls', 'stated', 'sibling', 'blank']);

const ratioOfMpp = (mpp) => (mpp > 0 ? Math.round((mpp * 72) / 0.0254) : 0);

/** The 1:N a PageScale is at, as a label ('~' for the areas' approximate one); '' without a scale. */
export function scaleLabelOf(pageScale) {
  const base = pageScale?.label || (ratioOfMpp(Number(pageScale?.metersPerPointX) || 0) ? `1:${ratioOfMpp(Number(pageScale.metersPerPointX))}` : '');
  return base && pageScale?.source === 'auto' ? `~${base}` : base;
}

/** A backend `masteliai[page]` record that carries provenance, or null. */
export function provenanceRecord(rec) {
  if (!rec || typeof rec !== 'object' || !BACKEND_SOURCES.includes(rec.saltinis)) return null;
  const out = { saltinis: rec.saltinis };
  for (const k of ['patikimumas', 'tekstas', 'pastaba']) if (typeof rec[k] === 'string' && rec[k]) out[k] = rec[k];
  if (Number(rec.is_lapo) > 0) out.is_lapo = Number(rec.is_lapo);
  return out;
}

/** Why sheet `page` has no scale, from `_meta.geometrija.masteliai_tusti` ('' when the lane did not say). */
export function blankReasonOf(project, page) {
  const tusti = project?._meta?.geometrija?.masteliai_tusti;
  if (!tusti || page == null) return '';
  const r = tusti[page] ?? tusti[String(page)];
  return typeof r === 'string' ? r.trim() : '';
}

// How many dimension strings the backend's note counts („139 matmenų eilutės …").
const countIn = (text) => {
  const m = /^(\d+)\s+matmenų eilut/.exec(String(text || ''));
  return m ? Number(m[1]) : 0;
};
// The scale(s) a sheet writes when its note says the dimensions contradict them („Lape užrašytas M 1:50, bet …",
// „Lape užrašytas mastelis 1:50, 1:100, bet …").
const writtenOtherIn = (note) => {
  const m = /užrašytas (?:mastelis |M )?(1:\d+(?:,\d+)?(?:, 1:\d+(?:,\d+)?)*)[^—]*?\b(?:bet|matmenys atitinka)/.exec(String(note || ''));
  return m ? m[1] : '';
};
const confirmsWritten = (text) => /sutampa su užrašytu M/.test(String(text || ''));
const readFromImage = (text) => /perskaityti iš lapo vaizdo/.test(String(text || ''));
const legacyWritten = (pageScale) => (pageScale?.uzrasyta || []).filter((n) => Number(n) > 0).map((n) => `1:${n}`).join(', ');

/** The phrase (without the label) for a backend provenance record → {key, params}. */
function backendPhrase(p, pageScale) {
  const conf = p.patikimumas;
  const written = writtenOtherIn(p.pastaba) || legacyWritten(pageScale);
  const n = countIn(p.tekstas);
  switch (p.saltinis) {
    case 'user_line':
      return p.tekstas ? { key: 'userLineText', params: { text: p.tekstas } } : { key: 'userLine' };
    case 'stated':
      if (conf === 'low') return { key: 'writtenUnchecked' };
      return p.is_lapo ? { key: 'writtenConfirmedSheet', params: { page: p.is_lapo } } : { key: 'writtenConfirmed' };
    case 'sibling':
      if (!p.is_lapo) return { key: 'siblingPlain' };
      return written ? { key: 'siblingWrittenOther', params: { page: p.is_lapo, written } } : { key: 'sibling', params: { page: p.is_lapo } };
    case 'dimension_lines':
    case 'dimension_walls': {
      if (conf === 'low') return { key: 'guessLow' };
      if (written) return { key: 'measuredWrittenOther', params: { written } };
      if (confirmsWritten(p.tekstas)) return { key: 'writtenConfirmed' };
      const base = p.saltinis === 'dimension_lines' ? 'lines' : 'walls';
      return n > 0 ? { key: base, params: { count: n } } : { key: `${base}Plain` };
    }
    default:
      return null;
  }
}

/**
 * Everything the UI says about one sheet's scale, as data:
 *   {state, line, label, phrase: {key, params}, notes: [{key, params} | {raw}], explain: [{key, params}]}
 *   state   nenustatytas · spejamas · nuskaitytas · patvirtintas
 *   line    'solid' (read or his) · 'dashed' (a proposal) · 'none'
 *   notes   what the card adds under the phrase (the backend's own note, read-from-image, an odd ratio)
 * `blankReason` = why there is none (blankReasonOf), shown only when no scale is in force.
 */
export function describeScale(pageScale, { blankReason = '' } = {}) {
  const calibrated = Boolean(pageScale?.calibrated) && Number(pageScale?.metersPerPointX) > 0;
  if (!calibrated) {
    return {
      state: 'nenustatytas', line: 'none', label: '',
      phrase: blankReason ? { key: 'noneReason', params: { reason: blankReason } } : { key: 'none' },
      notes: [], explain: [{ key: 'none' }],
    };
  }
  const label = scaleLabelOf(pageScale);
  const src = pageScale.source;
  const p = provenanceRecord(pageScale.provenance);
  const notes = [];
  if (p?.pastaba) notes.push({ raw: p.pastaba });
  if (p && readFromImage(p.tekstas)) notes.push({ key: 'ocr' });
  const ratio = ratioOfMpp(Number(pageScale.metersPerPointX));
  const lane = src === 'plan' || src === LANE_CONFIRMED;
  if (lane && ratio > 0 && !DRAWING_SCALES.includes(ratio) && !writtenOtherIn(p?.pastaba)) notes.push({ key: 'odd', params: { label } });

  if (src === 'user' || src === 'standard' || (src !== LANE_CONFIRMED && pageScale.confirmed === true && !lane)) {
    return { state: src === 'standard' ? 'spejamas' : 'patvirtintas', line: src === 'standard' ? 'dashed' : 'solid', label,
      phrase: { key: src === 'standard' ? 'userPicked' : 'userKnown' }, notes: [], explain: [{ key: 'user' }] };
  }
  if (src === 'auto') {
    return { state: 'spejamas', line: 'dashed', label, phrase: { key: 'auto' }, notes: [], explain: [{ key: 'auto' }] };
  }
  if (lane) {
    let phrase = p ? backendPhrase(p, pageScale) : null;
    const read = Boolean(phrase) && p.patikimumas !== 'low';
    if (!phrase) {
      const written = legacyWritten(pageScale);
      phrase = written ? { key: 'legacyWrittenOther', params: { written } } : { key: 'legacy' };
    }
    if (src === LANE_CONFIRMED || pageScale.confirmed === true) {
      const confirmed = read ? { key: 'confirmed', params: { phrase }, nested: true } : { key: 'confirmedPlain' };
      return { state: 'patvirtintas', line: 'solid', label, phrase: confirmed, notes, explain: [{ key: 'confirmed' }] };
    }
    return read
      ? { state: 'nuskaitytas', line: 'solid', label, phrase, notes, explain: [{ key: 'nuskaitytas' }] }
      : { state: 'spejamas', line: 'dashed', label, phrase, notes, explain: [{ key: 'spejamas' }] };
  }
  return { state: 'spejamas', line: 'dashed', label, phrase: { key: 'legacy' }, notes: [], explain: [{ key: 'spejamas' }] };
}

/** The state alone — what tools and counts branch on. */
export function provenanceState(pageScale) {
  return describeScale(pageScale).state;
}

// The chip's few words for each phrase (the chip shares the drawing's bottom edge with the tool pill, so the
// full phrase — with its count or the scale it contradicts — is the card's first line, not the chip's).
const SHORT = {
  none: 'none', noneReason: 'none',
  lines: 'lines', linesPlain: 'lines', walls: 'walls', wallsPlain: 'walls',
  writtenConfirmed: 'writtenConfirmed', writtenConfirmedSheet: 'writtenConfirmed', writtenUnchecked: 'writtenUnchecked',
  measuredWrittenOther: 'measured', sibling: 'sibling', siblingWrittenOther: 'sibling', siblingPlain: 'siblingPlain',
  userLine: 'userLine', userLineText: 'userLine', userKnown: 'user', userPicked: 'user',
  auto: 'guess', guessLow: 'guess', legacy: 'guess', legacyWrittenOther: 'guess',
  confirmed: 'confirmed', confirmedPlain: 'confirmed',
};

/** The chip's few words: „iš plano matmenų" / „užrašytas, nepatikrintas" / „spėjamas" / „iš 1 lapo". */
export function provenanceShort(desc, t) {
  const key = SHORT[desc?.phrase?.key] || 'guess';
  return t(`${NS}.short.${key}`, desc?.phrase?.params?.page != null ? { page: desc.phrase.params.page } : {});
}

function phraseText(phrase, t) {
  if (!phrase) return '';
  const params = { ...(phrase.params || {}) };
  if (phrase.nested && params.phrase) params.phrase = phraseText(params.phrase, t);
  return t(`${NS}.phrase.${phrase.key}`, params);
}

/** The phrase without the scale: „iš plano matmenų (139 skaičiai)" / „mastelio nėra — …". */
export function provenancePhrase(desc, t) {
  return phraseText(desc?.phrase, t);
}

/** „1:75 — iš plano matmenų (139 skaičiai)"; with no scale, „mastelio nėra — <why>". */
export function provenanceText(desc, t) {
  const phrase = provenancePhrase(desc, t);
  if (!desc?.label) return phrase;
  return t(`${NS}.withLabel`, { label: desc.label, phrase });
}

/** The card's explanation: what the state means, then the backend's own notes. */
export function provenanceExplanation(desc, t) {
  const parts = (desc?.explain || []).map((e) => t(`${NS}.explain.${e.key}`, e.params || {}));
  for (const n of desc?.notes || []) parts.push(n.raw ? n.raw : t(`${NS}.explain.${n.key}`, n.params || {}));
  return parts.filter(Boolean).join(' ');
}

/** The state in a word, for badges: nenustatytas · spėjamas · iš brėžinio · patvirtintas. */
export function scaleStateWord(state, t) {
  return t(`${NS}.state.${state}`);
}

/** One sheet straight to words — the status bar's line: „Mastelis 1:75 — iš plano matmenų (139 skaičiai)". */
export function scaleProvenanceLine(pageScale, t, opts = {}) {
  const desc = describeScale(pageScale, opts);
  const text = provenanceText(desc, t);
  if (desc.state === 'nenustatytas') return text.charAt(0).toUpperCase() + text.slice(1);
  return t(`${NS}.status.line`, { text });
}
