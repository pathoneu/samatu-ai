export function getSymbolPoints(result) {
  if (!result) return [];
  const isTemplate = result.symbol_type === 'template_symbol';
  const rawPoints = result.by_type
    ? Object.entries(result.by_type).flatMap(([type, info]) => (
      (info?.symbols || []).map(point => ({ ...point, type }))
    ))
    : (result.matches || result.symbols || []).map(point => ({
      ...point,
      type: result.symbol_type || point.type || 'symbol',
    }));

  return rawPoints.filter(point => {
    const x = Number(point.x_pct);
    const y = Number(point.y_pct);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return false;
    if (x < 0 || x > 1 || y < 0 || y > 1) return false;
    const confidence = String(point.confidence || 'medium').toLowerCase();
    if (confidence === 'high') return true;
    return confidence === 'medium';
  }).map(point => ({
    ...point,
    x_pct: Number(point.x_pct),
    y_pct: Number(point.y_pct),
    confidence: point.confidence || 'medium',
  }));
}

export function getSymbolVisibleCount(result) {
  return getSymbolPoints(result).length;
}

export function getConfirmableSymbolCounts(result) {
  const counts = {};
  for (const point of getSymbolPoints(result)) {
    const type = point.type || result?.symbol_type || 'symbol';
    counts[type] = (counts[type] || 0) + 1;
  }
  return Object.fromEntries(Object.entries(counts).filter(([, count]) => count > 0));
}

function samePoint(a, b) {
  return Number(a?.x_pct) === Number(b?.x_pct)
    && Number(a?.y_pct) === Number(b?.y_pct)
    && String(a?.confidence || 'medium').toLowerCase() === String(b?.confidence || 'medium').toLowerCase();
}

export function removeSymbolPoint(result, filteredIndex) {
  if (!result || filteredIndex < 0) return result;
  const target = getSymbolPoints(result)[filteredIndex];
  if (!target) return result;

  if (result.by_type) {
    const byType = {};
    for (const [type, info] of Object.entries(result.by_type)) {
      let removed = false;
      const symbols = (info?.symbols || []).filter(point => {
        if (!removed && type === target.type && samePoint(point, target)) {
          removed = true;
          return false;
        }
        return true;
      });
      byType[type] = { ...info, symbols, count: symbols.length };
    }
    const count = Object.values(byType).reduce((sum, info) => sum + (info?.symbols || []).length, 0);
    return { ...result, by_type: byType, count };
  }

  const key = result.matches ? 'matches' : 'symbols';
  let removed = false;
  const points = (result[key] || []).filter(point => {
    if (!removed && samePoint(point, target)) {
      removed = true;
      return false;
    }
    return true;
  });
  return { ...result, [key]: points, count: points.length };
}
