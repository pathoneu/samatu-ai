/**
 * mergeDarbuSarasas — carry the user's manual edits onto a freshly-rebuilt
 * darbu_sarasas. The JS twin of backend `api/recompute_quantities._merge_user_edits`.
 *
 * Extracted from InteriorProject.jsx 2026-07-28 so the merge is unit-testable
 * (this codebase's convention: testable logic lives in lib/, the page keeps a
 * thin call).
 *
 * WHY IT MATTERS (P0, 2026-07-28): the old pass 3 carried an unmatched prior row
 * only when it was tagged `source: 'Pažymėjus brėžinyje'` or `manual_override`.
 * Measured against the real demo blob on the /recompute-interior path, that
 * deleted 15 fully-priced rows worth 5 281,85 € — whole 'Elektros instaliacijos'
 * and 'Ventiliacijos' sections plus both 'Glaistymo kampai' lines — on a plain
 * room edit, silently. Now EVERY unmatched prior row is carried and flagged
 * `_orphaned_after_rebuild`.
 *
 * The single exception mirrors the backend: an un-edited row whose work is still
 * in the list under a sibling HEIGHT-TIER label ('… (virš 3m aukščio)' →
 * '… (iki 3m aukščio)') was re-tiered by the rebuild, not deleted — carrying it
 * would pin a stale duplicate of a quantity that legitimately moved. A row
 * carrying real money is carried even then: deciding that a user's priced line
 * is obsolete is not a call this merge gets to make silently.
 */

const _lc = (s) => (s || '').toLowerCase();

/**
 * 2026-09-02 sienų/lubų split — the JS twin of the backend's
 * `_PAINT_SPLIT_EXACT_RENAMES` (api/recompute_quantities.py). The combined
 * "Sienų, lubų glaistymas/dažymas …" line became one line per surface.
 *
 * Matched at the EXACT label, tier suffix included: the tier-stripped key
 * matches BOTH new tier lines, so `normLabel` (pass 2) would find it ambiguous
 * and refuse, and pass 3 would then carry the old priced row ALONGSIDE the new
 * ones — the same work twice, exactly the failure the LED consolidation caused
 * in 2026-07. Keep this map byte-identical to the backend's or the two merges
 * disagree and the duplicate comes back.
 */
const LEGACY_EXACT_RENAMES = {
  'sienų, lubų glaistymas/dažymas': 'sienų glaistymas/dažymas',
  'sienų, lubų glaistymas/dažymas (iki 3m aukščio)': 'sienų glaistymas/dažymas (iki 3m aukščio)',
  'sienų, lubų glaistymas/dažymas (virš 3m aukščio)': 'sienų glaistymas/dažymas (virš 3m aukščio)',
  'sienų, lubų šlifavimas q4 (80–120 grit, 100% paviršius)': 'sienų šlifavimas q4 (80–120 grit, 100% paviršius)',
};

/**
 * The same rename at the TIER-STRIPPED level — the JS twin of the backend's
 * `_PAINT_SPLIT_TIER_RENAMES`. The exact map above only fires on a full label,
 * which is what pass 1 needs; pass 2 works on `normLabel` keys, and without the
 * rename there a legacy priced '… (virš 3m aukščio)' row whose ceiling was
 * lowered normalized to a key NO rebuilt row carries — measured: the priced row
 * came back as an orphan and BOTH new rows came back unpriced. With it, pass 2's
 * one-to-one guard reunites it with the walls line and still refuses when two
 * tier lines share the key (that case belongs to pass 1, by exact label).
 */
const LEGACY_TIER_RENAMES = {
  'sienų, lubų glaistymas/dažymas': 'sienų glaistymas/dažymas',
  'sienų, lubų šlifavimas': 'sienų šlifavimas',
};

/** The section the shopping list lives in — mirror of `SK_MEDZIAGOS`. */
export const MEDZIAGOS_SKYRIUS = 'Medžiagos';

/**
 * Where a price CAME FROM. Travels with `kaina` everywhere the money travels,
 * because the UI's "hand-typed prices are left alone" guarantee is enforced on
 * `kaina_source` alone — a merge that drops it silently unprotects the price.
 * Mirror of the backend's `_PRICE_PROVENANCE_KEYS`.
 */
const PRICE_PROVENANCE_KEYS = ['kaina_source', 'kaina_match_score'];

/**
 * Stable-partition the shopping list to the foot of the sąmata. Mirror of the
 * backend's `_materials_last`.
 *
 * `SKYRIUS_ORDER[Medžiagos] = 11` is decorative — the builder appends the
 * section AFTER its sort — and pass 3 below appends carried orphans after
 * everything, so a priced orphan of a section that no longer exists sat BELOW
 * the shopping list that is supposed to close the sąmata.
 */
export function materialsLast(rows) {
  const work = [];
  const mats = [];
  for (const r of rows) {
    ((r?.skyrius || '') === MEDZIAGOS_SKYRIUS ? mats : work).push(r);
  }
  return mats.length ? work.concat(mats) : rows;
}

/**
 * Height/Q/coat-independent key: strip the 'iki/virš 3m' tier suffix, Q-level
 * and '(N sluoksnis)' so a price survives a label change on recompute (e.g. a
 * paint line flips iki<->virš 3m when a ceiling height crosses 3.0m). Used by
 * pass 2. Mirrors the backend's `_norm_label` fallback. (audit 2026-07-05)
 *
 * NOTE: deliberately does NOT fold the LED glaistymas/dažymas pair the way the
 * backend's `_norm_label` does — folding it here would let pass 2 consume a
 * priced 'LED nišų glaistymas' in favour of the consolidated line WITHOUT being
 * able to prove the price transferred. Verified 2026-07-28: un-folding is what
 * keeps 320 € on the books when the backend can't see the money.
 */
/**
 * Re-establish `id` uniqueness on the MERGE OUTPUT — the JS twin of the
 * backend's `_reassign_duplicate_ids` (api/recompute_quantities.py). The
 * builder mints unique ids for the rebuilt list only; pass 3 then appends
 * carried orphans keeping the ids they were saved with, and an orphan can
 * legitimately carry a live row's id (a priced legacy label whose id folds
 * onto its successor). Two rows with one id are indistinguishable to the
 * next merge's pass 0, to the ripple diff and to a React key.
 *
 * THE RULE (mirrors the backend exactly):
 *   · two claiming passes — first every row NOT flagged
 *     `_orphaned_after_rebuild`, in list order, then every carried orphan, in
 *     list order — so the rebuilt canonical row keeps the clean id and the
 *     orphan takes the suffix;
 *   · a row with no id is skipped (legacy blobs stay untouched);
 *   · claiming `base`: take it if free, else the first free `${base}-${n}`
 *     counting UP from n = 2 — counting up (not "position among duplicates")
 *     stays collision-free when an orphan already carries a `-2` id.
 * Returns a new array; rows that move get a copied object.
 */
/**
 * Verification („Teisinga ✓" / review status) certified a NUMBER, so it
 * survives a rebuild only when that number survived (±0,01) or the row is a
 * manual override the user owns. A row whose quantity moved returns to the
 * queue; the ripple shows it. Mirrors backend `_carry_verification`. Before
 * 2026-09-04 nothing carried these keys: one Prielaidos click erased every
 * checkmark on the project.
 */
export const VERIFICATION_KEYS = ['user_verified_at', '_review_status', '_review_status_at'];

function sameQuantity(a, b) {
  const x = Number(a); const y = Number(b);
  if (Number.isFinite(x) && Number.isFinite(y)) return Math.abs(x - y) <= 0.01;
  return a === b;
}

export function carryVerification(oldItem, out) {
  if (!oldItem || !VERIFICATION_KEYS.some((k) => oldItem[k] != null)) return out;
  const owned = out.manual_override === true || out.override_locked === true;
  if (owned || sameQuantity(oldItem.kiekis, out.kiekis)) {
    for (const k of VERIFICATION_KEYS) if (oldItem[k] != null) out[k] = oldItem[k];
  }
  return out;
}

export function reassignDuplicateIds(rows) {
  const used = new Set();
  const claim = (base) => {
    if (!used.has(base)) { used.add(base); return base; }
    let n = 2;
    while (used.has(`${base}-${n}`)) n += 1;
    const next = `${base}-${n}`;
    used.add(next);
    return next;
  };
  const out = (rows || []).slice();
  for (const orphans of [false, true]) {
    out.forEach((row, i) => {
      if (!row || typeof row !== 'object') return;
      if (Boolean(row._orphaned_after_rebuild) !== orphans) return;
      const base = String(row.id ?? '').trim();
      if (!base) return;
      const claimed = claim(base);
      if (claimed !== base) out[i] = { ...row, id: claimed };
    });
  }
  return out;
}

export function normLabel(s) {
  // Built on tierKey so both sides recognise the SAME tier vocabulary. Before
  // 2026-07-28 this stripped only the 'iki/virš 3m' suffix, so a rebuilt
  // '… (standartinis aukštis)' line kept a distinct key while the backend
  // folded it — the two normalizers disagreed and pass 2 assigned a price the
  // backend deliberately refuses to guess at (two rebuilt lines could own it).
  const base = tierKey(s);
  return (LEGACY_TIER_RENAMES[base] || base)
    .normalize('NFKD').replace(/[̀-ͯ]/g, '')             // drop accents
    .replace(/\bq[1-4]\b/g, '')                                    // drop Q-level
    .replace(/\(\s*\d+\s*sluoksn[^)]*\)/g, '')                     // drop '(N sluoksnis)'
    .replace(/\s+/g, ' ').trim();
}

/**
 * Label with ONLY the height/Q-level tier suffixes stripped — a 1:1 port of the
 * backend `_tier_key` / `_TIER_SUFFIX_RE`. Two labels sharing a tier key are the
 * same work at different ceiling tiers. Used by pass 3 to tell a re-tiered line
 * from one the rebuild simply cannot produce.
 */
export function tierKey(s) {
  return _lc(s)
    .replace(/\s*\((?:iki|vir[sš])\s*3\s*m[^)]*\)/g, '')           // (iki|virš 3m …)
    .replace(/\s*\(standartinis aukštis\)/g, '')                   // GKP tier label
    .replace(/\s*—\s*papildomas darbas dėl aukščio/g, '')          // height premium
    .replace(/\s*q4\s*\([^)]*\)/g, '')                             // Q4 sanding suffix
    .trim();
}

/** Does this row carry something of the user's that a rebuild must not destroy? */
export function hasUserEdit(p) {
  if (!p) return false;
  return (p.kaina != null && p.kaina !== 0)
    || p.manual_override === true
    || p.quantity_source === 'manual_override'
    || !!p.override_locked
    || p.source === 'Pažymėjus brėžinyje';   // user-added, drawing-marked line
}

/**
 * `hasUserEdit`, except that a price the KAINYNAS filled in is not the user's
 * hand. The JS twin of the backend's `_has_user_edit_beyond_kainynas`.
 *
 * THE OVER-BILLING (2026-09-02): pass 3 keeps a superseded tier line whenever
 * the row carries a user edit, and `hasUserEdit` reads ANY non-zero kaina as
 * one. That was harmless while rows arrived unpriced — the fold worked. Since
 * `autoFillFromDefaultPriceList` prices every matched row at extraction, EVERY
 * row looked edited: lowering a ceiling left the old '(virš 3m aukščio)' line on
 * the books next to its own re-tiered successor, and the client was billed
 * 240 m² of the 200 m² he has. An AI-matched price must not veto a fold; a
 * hand-typed one still does, and so do a corrected quantity and a gesture lock.
 */
export function hasUserEditBeyondKainynas(p) {
  if (!p) return false;
  if (p.kaina_source === 'kainynas') {
    return p.manual_override === true
      || p.quantity_source === 'manual_override'
      || !!p.override_locked
      || p.source === 'Pažymėjus brėžinyje';
  }
  return hasUserEdit(p);
}

/**
 * @param {Array}  rebuilt  freshly-computed rows from the backend
 * @param {Array}  old      the rows currently in the project (user's prices etc.)
 * @param {Array} [notes]   optional out-param: one entry per carried/suppressed
 *                          row, so the caller can DISCLOSE what wasn't recomputed
 * @param {Array} [serverRelabeled] labels the BACKEND already folded into a
 *                          rebuilt row (its `_merge_notes` reason:'relabeled').
 *                          Without this the row looks unmatched here and gets
 *                          carried ALONGSIDE the line it was folded into —
 *                          measured 2026-07-28: 320 € counted twice on the LED
 *                          consolidation. Only honoured when the target row is
 *                          actually present, so a bogus note can't eat money.
 * @returns {Array} merged rows
 */
/**
 * @param {object} [opts]
 * @param {boolean} [opts.scopeChange] — this rebuild followed a „ką skaičiuoti"
 *   choice (lib/scope.js). A prior row the builder no longer emits was removed
 *   ON PURPOSE (ceilings not his, a family off, a room switched off), so it is
 *   dropped rather than carried as an orphan — except the contractor's own
 *   rows (`rnk-`) and rows whose QUANTITY he typed (`manual_override`), which
 *   are never taken away by a recompute.
 */
export function mergeDarbuSarasasEdits(rebuilt, old, notes, serverRelabeled, opts = {}) {
  const scopeChange = !!(opts && opts.scopeChange);
  if (!Array.isArray(notes)) notes = [];
  if (!Array.isArray(rebuilt)) return old || [];
  const oldList = old || [];
  const oldByLabel = new Map();
  for (const o of oldList) {
    const k = _lc(o.aprasymas);
    if (!k) continue;
    if (!oldByLabel.has(k)) oldByLabel.set(k, o);
  }
  // Aliases in a SECOND pass. Registered in the loop above, a legacy row that
  // happens to come FIRST in the list claimed the post-split key and the user's
  // own row — the one already carrying that label — was carried back as an
  // orphan while the walls line inherited the legacy price. A row's own label
  // always wins; a rename only fills a key nobody claimed.
  for (const o of oldList) {
    const renamed = LEGACY_EXACT_RENAMES[_lc(o.aprasymas)];
    if (renamed && !oldByLabel.has(renamed)) oldByLabel.set(renamed, o);
  }
  const matchedOld = new Set();  // old items already consumed (by object identity)
  const matchedNew = new Set();  // rebuilt indexes already matched by pass 0
  // Rows the server folded into another line are already represented (with
  // their price) in `rebuilt` — consume them so neither pass re-uses them.
  if (Array.isArray(serverRelabeled) && serverRelabeled.length) {
    const rebuiltLabels = new Set(rebuilt.map((r) => _lc(r.aprasymas)));
    for (const n of serverRelabeled) {
      const from = _lc(typeof n === 'string' ? n : n?.aprasymas);
      const into = _lc(typeof n === 'string' ? null : n?.into);
      if (!from) continue;
      if (into && !rebuiltLabels.has(into)) continue;   // target missing → keep the row
      const o = oldByLabel.get(from);
      if (o && !rebuiltLabels.has(from)) {
        matchedOld.add(o);
        notes.push({ reason: 'relabeled_by_server', aprasymas: o.aprasymas });
      }
    }
  }
  const carry = (newItem, oldItem) => {
    const keepQty = oldItem.manual_override === true
      || oldItem.quantity_source === 'manual_override';
    const kiekis = keepQty ? oldItem.kiekis : newItem.kiekis;
    const kaina = oldItem.kaina ?? newItem.kaina;
    const out = { ...newItem };
    if (keepQty) {
      out.kiekis = kiekis;
      out.manual_override = true;
      out.quantity_source = 'manual_override';
      if (oldItem.ai_kiekis_original != null) out.ai_kiekis_original = oldItem.ai_kiekis_original;
    }
    if (kaina != null) {
      out.kaina = kaina;
      out.suma = (kiekis || 0) * kaina;
      // …WITH its provenance. `kaina_source` was in neither carry set, so a
      // hand-typed price came back from the first recompute unlabelled and the
      // next „Taikyti kainyną" overwrote it — the exact opposite of what that
      // button's own footnote promises. It also tells pass 3 whether a price is
      // the user's hand or the kainynas's guess.
      for (const key of PRICE_PROVENANCE_KEYS) {
        if (oldItem[key] != null) out[key] = oldItem[key];
      }
    }
    carryVerification(oldItem, out);
    return out;
  };
  // Pass 0 — stable id (2026-09-02, Patikra P0). The JS twin of the backend's
  // id pass. Both sides carry `id` only when both came out of the current
  // builder (`extractor/position_id.py`), so this is a no-op on every project
  // saved before ids existed and the label passes below remain the fallback
  // forever. The id already folds the same renames the label maps above spell
  // out, so it agrees with them rather than racing them.
  const merged = rebuilt.slice();
  const oldById = new Map();
  for (const o of oldList) {
    const k = String(o?.id || '').trim();
    if (k && !oldById.has(k)) oldById.set(k, o);
  }
  if (oldById.size) {
    merged.forEach((newItem, i) => {
      const k = String(newItem?.id || '').trim();
      if (!k) return;
      const oldItem = oldById.get(k);
      if (!oldItem || matchedOld.has(oldItem)) return;
      matchedOld.add(oldItem);
      matchedNew.add(i);
      merged[i] = carry(newItem, oldItem);
      if (_lc(oldItem.aprasymas) !== _lc(newItem.aprasymas)) {
        notes.push({
          reason: 'relabeled',
          aprasymas: oldItem.aprasymas,
          into: newItem.aprasymas,
        });
      }
    });
  }
  // Pass 1 — exact lowercased-label match (unchanged behaviour).
  merged.forEach((newItem, i) => {
    if (matchedNew.has(i)) return;
    const oldItem = oldByLabel.get(_lc(newItem.aprasymas));
    if (!oldItem || matchedOld.has(oldItem)) return;
    matchedOld.add(oldItem);
    merged[i] = carry(newItem, oldItem);
  });
  // Pass 2 — rescue prices for lines whose label changed on rebuild. Match
  // still-unpriced rebuilt lines to unconsumed old PRICED/edited lines by the
  // normalized key, applied ONLY when unambiguous (one-to-one) so it can never
  // mis-assign a price between two co-existing tier lines.
  const push = (m, k, v) => { const a = m.get(k) || []; a.push(v); m.set(k, a); };
  const oldByNorm = new Map();
  for (const o of oldList) {
    if (matchedOld.has(o)) continue;
    if (o.kaina == null && o.manual_override !== true) continue;
    const k = normLabel(o.aprasymas); if (k) push(oldByNorm, k, o);
  }
  const newByNorm = new Map();
  merged.forEach((m, i) => {
    if (m.kaina != null) return;
    const k = normLabel(m.aprasymas); if (k) push(newByNorm, k, i);
  });
  for (const [k, idxs] of newByNorm) {
    const cands = oldByNorm.get(k) || [];
    if (idxs.length === 1 && cands.length === 1) {
      merged[idxs[0]] = carry(merged[idxs[0]], cands[0]);
      matchedOld.add(cands[0]);
      if (_lc(cands[0].aprasymas) !== _lc(merged[idxs[0]].aprasymas)) {
        notes.push({
          reason: 'relabeled',
          aprasymas: cands[0].aprasymas,
          into: merged[idxs[0]].aprasymas,
        });
      }
    }
  }
  // Pass 3 — carry (don't delete) every still-unmatched prior row. Computed from
  // the ORIGINAL rebuilt list so a carried orphan can never suppress a later one.
  const rebuiltTierKeys = new Set();
  for (const r of rebuilt) {
    const k = tierKey(r.aprasymas);
    if (k) rebuiltTierKeys.add(k);
  }
  for (const o of oldList) {
    if (matchedOld.has(o)) continue;
    // `edited` decides whether a row survives being superseded; `hasMoney` is
    // what the user is TOLD about. They differ on exactly one row: a line the
    // kainynas priced, which carries money but is not a reason to keep a
    // duplicate of work that legitimately moved tier.
    const edited = hasUserEditBeyondKainynas(o);
    const hasMoney = hasUserEdit(o);
    if (!edited && rebuiltTierKeys.has(tierKey(o.aprasymas))) {
      // Un-edited line whose work is still listed under a sibling tier label —
      // the rebuild re-tiered it, nothing was lost.
      notes.push({ reason: 'superseded_by_tier', aprasymas: o.aprasymas });
      continue;
    }
    if (String(o.id || '').startsWith('rnk-')) {
      // Hand-added row: never rebuilt by construction, so it is kept as-is —
      // not flagged „pasenusi eilutė" (2026-09-04 UX audit). Mirrors backend.
      const { _orphaned_after_rebuild: _drop, ...kept } = o;
      merged.push(kept);
      notes.push({ reason: 'manual_row_kept', aprasymas: o.aprasymas });
      continue;
    }
    if (scopeChange && o.manual_override !== true && o.quantity_source !== 'manual_override') {
      // The builder left this row out because of what he just chose — that is
      // the point of the choice, not a loss to paper over.
      notes.push({ reason: 'dropped_by_scope', id: o.id, aprasymas: o.aprasymas, kiekis: o.kiekis, kaina: o.kaina });
      continue;
    }
    merged.push({ ...o, _orphaned_after_rebuild: true });
    notes.push({
      reason: 'orphan_carried',
      id: o.id,
      aprasymas: o.aprasymas,
      kiekis: o.kiekis,
      kaina: o.kaina,
      user_edit: hasMoney,
    });
  }
  return reassignDuplicateIds(materialsLast(merged));
}

/** Rows a „ką skaičiuoti" choice took out of the sąmata. */
export function droppedByScope(notes) {
  return (notes || []).filter((n) => n && n.reason === 'dropped_by_scope');
}

/** Rows the rebuild could not reproduce — the ones the user must be told about. */
export function carriedOrphans(notes) {
  return (notes || []).filter((n) => n && n.reason === 'orphan_carried');
}

/**
 * Only the rows that became orphans THIS rebuild. A row already flagged
 * `_orphaned_after_rebuild` in the prior list is carried again every time —
 * announcing it every time turned a one-off notice into a permanent alarm on
 * every project built by an older engine (2026-09-04: "30 pozicijų nebuvo
 * perskaičiuotos" on every Prielaidos toggle). Labels are matched by id when
 * both sides carry one, else by label.
 */
export function newlyCarriedOrphans(notes, priorRows) {
  const priorOrphanIds = new Set();
  const priorOrphanLabels = new Set();
  (priorRows || []).forEach((r) => {
    if (!r || !r._orphaned_after_rebuild) return;
    if (r.id) priorOrphanIds.add(String(r.id));
    priorOrphanLabels.add(_lc(r.aprasymas));
  });
  return carriedOrphans(notes).filter((n) =>
    !(n.id && priorOrphanIds.has(String(n.id))) && !priorOrphanLabels.has(_lc(n.aprasymas)));
}

export default mergeDarbuSarasasEdits;
