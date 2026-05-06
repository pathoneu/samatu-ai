export const PLAN_MIN_SCALE = 0.35;
export const PLAN_MAX_SCALE = 2.5;

export function clampPlanScale(scale) {
  const n = Number(scale);
  if (!Number.isFinite(n)) return 1;
  return Number(Math.max(PLAN_MIN_SCALE, Math.min(PLAN_MAX_SCALE, n)).toFixed(2));
}

export function getNextPlanPage(currentPage, delta, totalPages) {
  const total = Math.max(1, Number(totalPages) || 1);
  const current = Math.max(1, Number(currentPage) || 1);
  return Math.max(1, Math.min(total, current + delta));
}

export function getPlanFitScale({ mode, viewportWidth, viewportHeight, page }) {
  if (!page?.width || !page?.height || !viewportWidth || !viewportHeight) return 1;
  const chromePadding = mode === 'page' ? 72 : 80;
  const widthScale = (viewportWidth - chromePadding) / page.width;
  const heightScale = (viewportHeight - chromePadding) / page.height;
  const raw = mode === 'page' ? Math.min(widthScale, heightScale) : widthScale;
  return clampPlanScale(raw);
}

export function getVisiblePlanPages({ totalPages = 0, pageMeta = {}, query = '' }) {
  const normalizedQuery = String(query || '').trim().toLowerCase();
  const count = Math.max(0, Number(totalPages) || 0);
  const pages = Array.from({ length: count }, (_, idx) => {
    const nr = idx + 1;
    const meta = pageMeta[nr] || {};
    return {
      nr,
      label: meta.label || `Puslapis ${nr}`,
      type: meta.type || 'unknown',
      confidence: meta.confidence,
    };
  });
  if (!normalizedQuery) return pages;
  return pages.filter((page) => {
    const haystack = `${page.nr} ${page.label} ${page.type}`.toLowerCase();
    return haystack.includes(normalizedQuery);
  });
}

export function getDefaultPlanPage({ totalPages = 0, pageMeta = {} }) {
  const count = Math.max(0, Number(totalPages) || 0);
  for (let nr = 1; nr <= count; nr += 1) {
    if (pageMeta[nr]?.type === 'floor_plan') return nr;
  }
  for (let nr = 1; nr <= count; nr += 1) {
    const type = pageMeta[nr]?.type;
    if (type && !['title_page', 'non_relevant', 'unknown'].includes(type)) return nr;
  }
  return count > 0 ? 1 : null;
}
