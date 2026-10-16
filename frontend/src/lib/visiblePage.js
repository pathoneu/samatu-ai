// The page the user is actually LOOKING at. The scroll plugin's `currentPage`
// goes stale under wheel-scrolling (audit P1: "psl. 2" while page 3 fills the
// screen; fit then yanks the viewport back) while pageVisibilityMetrics stay
// live — virtualization depends on them — so derive from the metrics and fall
// back to the plugin's field. (Moved out of TakeoffViewer 2026-10-16 so the
// scale panel and chip read the same page.)
export function visiblePageOf(scroll) {
  const m = scroll?.pageVisibilityMetrics;
  if (Array.isArray(m) && m.length) {
    let best = m[0];
    for (const x of m) if (x.visiblePercentage > best.visiblePercentage) best = x;
    return best.pageNumber;
  }
  return scroll?.currentPage ?? 1;
}
