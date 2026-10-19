/**
 * legendCounts — what the drawing's legend counts say, by kind of thing, for the row builder (Pathon v3 W5-D, (a)).
 *
 * A count type made from a legend row (v3 W2-B: it carries `legend_row_id` and `legend_text`) and its marks on the
 * drawing become `_legendos_kiekiai` = {kind: {kiekis, tekstas, row_id, page, eilutes}} — the contract in
 * backend/extractor/fixture_rows_flag.py (W5-E's „Trapų montavimas" row reads `trapai`). The kind is the legend
 * row's text folded to a small, fixed vocabulary (KINDS); a row whose text names none of them is left out — the
 * builder only ever looks a kind up. Two legend rows of one kind (a floor drain and a linear drain) add up: both
 * are pieces of that kind counted on the drawing. A type with no marks counts nothing and is left out.
 *
 * Sent on every recompute (lib/recomputeContext.js), so a recount, a mark removed or Atšaukti reaches the rows
 * the next time they are rebuilt — never a stale copy. Undefined when there is nothing to say: the request
 * stays byte-identical. Pure.
 */

const fold = (s) => String(s || '')
  .toLowerCase()
  .normalize('NFD')
  .replace(/[̀-ͯ]/g, '');

// kind → what a legend row's text says for it (folded: no diacritics). Order matters: the first match wins.
export const KINDS = Object.freeze([
  ['trapai', /\btrap|\bdrenaz/],
  ['difuzoriai', /difuzor/],
  ['davikliai', /davikl|detektor/],
  ['jungikliai', /jungikl|perjung/],
  ['rozetes', /rozet|lizd/],
  ['sviestuvai', /sviestuv/],
]);

export function legendKind(text) {
  const t = fold(text);
  if (!t.trim()) return null;
  const hit = KINDS.find(([, re]) => re.test(t));
  return hit ? hit[0] : null;
}

export function legendCounts(project) {
  const types = Array.isArray(project?.countTypes) ? project.countTypes : [];
  const marks = Array.isArray(project?.measurements) ? project.measurements : [];
  const out = {};
  for (const type of types) {
    if (!type?.legend_row_id || !type.id) continue;
    const text = String(type.legend_text || type.label || '').trim();
    const kind = legendKind(type.legend_text) || legendKind(type.label);
    if (!kind) continue;
    const own = marks.filter((m) => m?.kind === 'count' && m.typeId === type.id);
    if (!own.length) continue;
    const pages = own.map((m) => Number(m.page)).filter((p) => Number.isFinite(p)).sort((a, b) => a - b);
    const cur = out[kind];
    if (!cur) {
      out[kind] = { kiekis: own.length, tekstas: text, row_id: String(type.legend_row_id), page: pages[0] ?? null, eilutes: [text] };
    } else {
      cur.kiekis += own.length;
      cur.eilutes.push(text);
      cur.tekstas = cur.eilutes.join('; ');
      if (pages.length && (cur.page == null || pages[0] < cur.page)) cur.page = pages[0];
    }
  }
  return Object.keys(out).length ? out : undefined;
}
