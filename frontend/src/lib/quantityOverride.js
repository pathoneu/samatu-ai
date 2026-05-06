export function updatePositionQuantity(rows, rowId, quantity) {
  const kiekis = Number(quantity);
  if (!Number.isFinite(kiekis) || kiekis < 0) {
    throw new Error('Invalid quantity');
  }

  return (rows || []).map((row) => {
    const id = row._id || `${row.eil_nr}-${row.aprasymas}`;
    if (id !== rowId) return row;

    const originalAiQty = row.ai_kiekis_original ?? row.kiekis ?? 0;
    const kaina = Number(row.kaina || 0);
    return {
      ...row,
      kiekis,
      suma: kiekis * kaina,
      confidence: 'high',
      quantity_source: 'manual_override',
      manual_override: true,
      ai_kiekis_original: originalAiQty,
      manual_override_at: new Date().toISOString(),
    };
  });
}

export function adjustPositionQuantity(rows, rowId, delta) {
  const row = (rows || []).find((item) => {
    const id = item._id || `${item.eil_nr}-${item.aprasymas}`;
    return id === rowId;
  });
  const next = Math.max(0, Number(row?.kiekis || 0) + Number(delta || 0));
  return updatePositionQuantity(rows, rowId, next);
}

export function acceptPositionQuantity(rows, rowId) {
  return (rows || []).map((row) => {
    const id = row._id || `${row.eil_nr}-${row.aprasymas}`;
    if (id !== rowId) return row;
    return {
      ...row,
      confidence: 'high',
      quantity_source: row.quantity_source || 'user_verified_ai',
      user_verified_at: new Date().toISOString(),
    };
  });
}
