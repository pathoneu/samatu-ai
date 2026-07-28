/**
 * Sprint 0 Fix 2: delegate paint formula recompute to backend.
 *
 * Replaces hardcoded `*2/9, *2/10` from interiorCalc.js:187-188 which
 * ignored paint class and 1.8× absorption.
 */

import { API_BASE } from './apiBase.js';

export async function recompute({
  rooms, edits, current_assumptions, pozicijos, context, darbu_sarasas,
}) {
  const body = { rooms, edits, current_assumptions };
  // Sprint 2: pozicijos optional — assumption-class edits don't need it,
  // but G2/G3/G4/G7 gesture edits do. Forward when caller provides.
  if (pozicijos !== undefined) body.pozicijos = pozicijos;
  // 2026-06-17: reader/extraction context so an assumption edit (ceiling height)
  // rebuilds the canonical pozicijos without losing door/fixture/symbol lines.
  if (context !== undefined) body.context = context;
  // 2026-07-28 (P0): the user's PRICES live in darbu_sarasas, not in pozicijos
  // (real blobs: pozicijos 0/73 priced, darbu_sarasas 73/73). Without this the
  // backend merge can't tell a priced row from a throwaway one, so its
  // price-carry and tier-rescue passes never fire on real projects.
  if (darbu_sarasas !== undefined) body.darbu_sarasas = darbu_sarasas;
  const res = await fetch(`${API_BASE}/api/recompute-quantities`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `recompute failed: ${res.status}`);
  }
  return res.json();
}
