/**
 * LED niches whose length was not read off the drawing (2026-10-06).
 *
 * Where the niche reader found nothing, the backend puts an estimate from the
 * room type (`_source: 'statistical_inference'`, extractor/niche_inference.py).
 * Since 2026-10-06 that estimate is not billed until the contractor accepts it
 * in Nustatymai (`_overrides.led_nisu_ivertinimas`); until then the sąmata
 * carries a blank row „LED nišos — suveskite ilgį" naming the same rooms.
 */

const ESTIMATED = 'statistical_inference';

/**
 * [{ label, metres }] in room order — read from the rooms' elements, so the
 * list is the same whether he has accepted the estimate or not. A room his
 * „ką skaičiuoti" took out (the whole room, or its finishing) is left out, the
 * same rooms the backend's blank row leaves out.
 */
export function estimatedLedRooms(rooms) {
  const out = [];
  for (const r of rooms || []) {
    if (!r || r._neskaiciuoti || (r._neskaiciuoti_sritys || []).includes('apdaila')) continue;
    const metres = (r.elementai || [])
      .filter((e) => e && e._source === ESTIMATED && String(e.tipas || '').toLowerCase() === 'nisa_led')
      .reduce((s, e) => s + Math.max(0, Number(e.ilgis_m) || 0), 0);
    if (metres > 0) {
      out.push({ label: String(r.nr || r.pavadinimas || '?').trim(), metres: Math.round(metres * 100) / 100 });
    }
  }
  return out;
}

/**
 * Is the estimate in the niche rows right now? His answer when he gave one
 * (`_overrides.led_nisu_ivertinimas`); otherwise what the rooms say: a room
 * whose estimate waits carries `_nisu_ivertinta_m` (backend
 * vision_call.refresh_led_metres). A project computed before 2026-10-06 has
 * no such room and still bills the estimate until its next recompute — the
 * choice must show that, not the new default its rows do not follow yet.
 */
export function ledEstimateBilled(rooms, answer) {
  if (answer === true || answer === false) return answer;
  const waiting = (r) => Number(r?._nisu_ivertinta_m) > 0;
  const withEstimate = (rooms || []).filter((r) => r && !r._neskaiciuoti
    && !(r._neskaiciuoti_sritys || []).includes('apdaila')
    && (r.elementai || []).some((e) => e && e._source === ESTIMATED && Number(e.ilgis_m) > 0));
  return withEstimate.length > 0 && !withEstimate.some(waiting);
}

const lt = (v) => Number(v).toFixed(2).replace('.', ',');

/** „103 (7,70 m), 106 (6,30 m)" and the total „14,00" — his decimal commas. */
export function ledEstimateText(list) {
  const items = list || [];
  return {
    rooms: items.map((x) => `${x.label} (${lt(x.metres)} m)`).join(', '),
    total: lt(items.reduce((s, x) => s + x.metres, 0)),
  };
}
