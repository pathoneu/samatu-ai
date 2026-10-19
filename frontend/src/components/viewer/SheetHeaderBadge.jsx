/**
 * SheetHeaderBadge — the sheet on screen, named the way the drawing names it (Pathon v3 W5-B, B1; coverage #8,
 * #9): its badge („B.01", else the page number), its name and „← 3 iš 8 →". The arrows, PageUp / PageDown and
 * „[" / „]" step one sheet (lib/viewerShortcuts). The first card of the top row, left of the reading / search
 * card; it keeps `data-nav-cluster` so the chrome placement (useChromeRects „nav") still finds the top row.
 *
 * The model is lib/sheetHeader (pure, tested); the sheet names come from the sheet rail's model, so a sheet he
 * renamed in the rail is named here too.
 */
import { useScroll } from '@embedpdf/plugin-scroll/react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { sheetHeaderModel } from '@/lib/sheetHeader';
import { visiblePageOf } from '@/lib/visiblePage';
import { withKey } from '@/lib/viewerShortcuts';

const btn = 'h-8 min-w-8 px-1.5 inline-flex items-center justify-center rounded text-viewer-chrome-foreground hover:bg-viewer-chrome-hover disabled:opacity-40 disabled:hover:bg-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

export default function SheetHeaderBadge({ documentId, totalPages, sheets = null, className = '' }) {
  const { state: scroll, provides: scrollApi } = useScroll(documentId);
  const m = sheetHeaderModel({ page: visiblePageOf(scroll), total: totalPages, sheets });
  // Deterministic: jump to the visible page ± 1 (the plugin's own next/previous steps from its stale currentPage).
  const go = (pageNumber) => scrollApi?.scrollToPage({ pageNumber });
  return (
    <div
      className={`pointer-events-auto rounded-panel border border-border bg-card shadow-md flex items-center gap-1 px-1 py-1 min-w-0 ${className}`}
      data-nav-cluster
      data-sheet-badge
      role="group"
      aria-label={m.title}
    >
      <span
        className="shrink-0 mono tabular text-ui font-semibold text-foreground px-1.5 py-0.5 rounded-[2px] border border-border bg-muted"
        title={m.title}
        data-testid="sheet-badge"
      >{m.badge}</span>
      <span className="min-w-0 max-w-[220px] truncate text-ui text-foreground px-0.5" title={m.title} data-testid="sheet-name">{m.name}</span>
      <span aria-hidden="true" className="w-px h-5 bg-border mx-0.5 shrink-0" />
      <button type="button" className={btn} title={withKey('Ankstesnis lapas', 'prevPage')} aria-label="Ankstesnis lapas" disabled={!m.canPrev} onClick={() => go(m.prev)} data-testid="sheet-prev">
        <ChevronLeft className="w-4 h-4" />
      </button>
      <span className="mono tabular text-ui text-foreground whitespace-nowrap" data-testid="sheet-pager">{m.pager}</span>
      <button type="button" className={btn} title={withKey('Kitas lapas', 'nextPage')} aria-label="Kitas lapas" disabled={!m.canNext} onClick={() => go(m.next)} data-testid="sheet-next">
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}
