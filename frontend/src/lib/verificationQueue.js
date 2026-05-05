// frontend/src/lib/verificationQueue.js
/**
 * Sprint 3: verification queue builder + helpers.
 *
 * The wizard panel reads a queue of {id, label, kiekis, vnt, polygon,
 * dispute_type, skipped} items derived from rooms+pozicijos. Order:
 * 🔴 (low) first, then 🟡 (med). 🟢 (high) auto-trusted (never queued).
 * Locked items (override_locked) skipped — already user-confirmed.
 *
 * Spec §4.5 (data flow) + §5.3 (wizard mechanics).
 */

const CONFIDENCE_RANK = { low: 0, med: 1, high: 2 }; // 🔴 sorts before 🟡

export function classifyDispute(poz) {
  // Number disputes (m², m³, m, kg, l) → bottom-panel inline editor
  // Count disputes (vnt in elektra/santechnika) → canvas G2/G3 cursor
  // Default: number (safer — wizard offers inline edit)
  const vnt = (poz.vnt || '').toLowerCase();
  const skyrius = (poz.skyrius || '').toLowerCase();
  if (vnt === 'vnt' && (skyrius === 'elektra' || skyrius === 'santechnika')) {
    return 'count';
  }
  return 'number';
}

export function buildQueue({ rooms = [], pozicijos = [], skipped = new Set() }) {
  const roomById = new Map();
  for (const r of rooms) {
    if (r.id) roomById.set(r.id, r);
  }

  const items = [];
  for (const p of pozicijos) {
    if (p.override_locked) continue;          // already confirmed
    const conf = (p.confidence || 'med').toLowerCase();
    if (conf === 'high') continue;             // auto-trust 🟢
    const room = p.room_id ? roomById.get(p.room_id) : null;
    items.push({
      id: p.id,
      label: `${p.skyrius_label || p.skyrius || ''} · ${p.aprasymas || ''}`.trim(),
      kiekis: p.kiekis,
      vnt: p.vnt,
      confidence: conf,
      polygon: room?.polygon_pct ?? null,
      dispute_type: classifyDispute(p),
      skipped: skipped.has(p.id),
      saltinis: p.saltinis || null,
    });
  }

  // Stable sort: 🔴 first, then 🟡 in original order
  items.sort((a, b) => CONFIDENCE_RANK[a.confidence] - CONFIDENCE_RANK[b.confidence]);
  return items;
}

export function advanceQueue(currentIndex, length) {
  return Math.min(currentIndex + 1, length);
}

export function isQueueComplete(currentIndex, length) {
  return currentIndex >= length;
}
