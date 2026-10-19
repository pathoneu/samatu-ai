/**
 * CalloutLayer — references on this sheet to other sheets („žr. lapą 3", „žiūrėti iškl.", an
 * elevation tag „g2"), drawn as subtle link underlines (Togal-v2 W7). A click scrolls the viewer
 * to the sheet the span means; hovering says which one: „→ lapas 11: Išklotinės a1-a9".
 *
 * The spans come from GET …/pages/{page}/callouts (api/sheet_links.py: the PDF's text layer,
 * matched against the sheet names, no AI), fetched once per (project, page, names version) by
 * lib/sheetLinksApi. Boxes are display-frame page fractions — the frame room outlines live in —
 * so they are plotted against the rendered page size like RoomZoneLayer's.
 *
 * Interactive only while no tool owns the pointer: a measurement must never jump to another sheet.
 */
import { useEffect, useState } from 'react';
import { useScroll } from '@embedpdf/plugin-scroll/react';
import { fetchPageCallouts } from '@/lib/sheetLinksApi';
import { calloutHoverText } from '@/lib/sheetRail';

const MIN_HIT_PX = 14;   // a 2-character tag at fit-to-width is ~5 × 6 px — keep it clickable both ways

export function usePageCallouts(projectId, page, version, enabled) {
  const [callouts, setCallouts] = useState([]);
  useEffect(() => {
    if (!enabled || !projectId || !(page >= 1)) return undefined;
    let alive = true;
    fetchPageCallouts(projectId, page, version)
      .then((body) => { if (alive) setCallouts(Array.isArray(body?.callouts) ? body.callouts : []); })
      .catch(() => { if (alive) setCallouts([]); });   // no PDF, a scan, a 429 — no links, never a toast
    return () => { alive = false; };
  }, [projectId, page, version, enabled]);
  return callouts;
}

export default function CalloutLayer({ documentId, projectId, page, version = '', renderedSize, sheets = [], interactive = true }) {
  const callouts = usePageCallouts(projectId, page, version, true);
  const { provides: scrollApi } = useScroll(documentId);
  const [hover, setHover] = useState(null);
  const { width, height } = renderedSize || {};
  if (!callouts.length || !width || !height) return null;

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} data-testid="callout-layer">
      {callouts.map((c, i) => {
        const [x0, y0, x1, y1] = c.bbox_pct || [];
        if (![x0, y0, x1, y1].every(Number.isFinite)) return null;
        const textW = Math.max((x1 - x0) * width, 2);
        const w = Math.max(textW, MIN_HIT_PX);
        const left = x0 * width - (w - textW) / 2;
        const textH = Math.max((y1 - y0) * height, 2);
        const hitH = Math.max(textH, MIN_HIT_PX);
        const top = y0 * height - (hitH - textH) / 2;
        const label = calloutHoverText(c, sheets);
        return (
          <button
            key={`${i}-${c.target_page}`}
            type="button"
            aria-label={label}
            data-callout-target={c.target_page}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation();
              scrollApi?.scrollToPage({ pageNumber: Number(c.target_page), behavior: 'smooth' });
            }}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover((h) => (h === i ? null : h))}
            onFocus={() => setHover(i)}
            onBlur={() => setHover((h) => (h === i ? null : h))}
            style={{
              position: 'absolute', left, top, width: w, height: hitH,
              pointerEvents: interactive ? 'auto' : 'none',
              cursor: 'pointer', background: 'transparent', padding: 0, border: 0,
            }}
            className="group/callout focus:outline-none"
          >
            {/* the words themselves: a faint evergreen tint and a 2 px underline — solid when the sheet was
                read for sure, the one dash when several sheets could be meant (an estimate; v3 overlay
                vocabulary) — visible on a busy plan, quiet on a clean one */}
            <span
              style={{ position: 'absolute', left: (w - textW) / 2, width: textW, top: (hitH - textH) / 2, height: textH + 1 }}
              className={`block rounded-[1px] border-b-2 ${c.confidence === 'low' ? 'border-dashed' : 'border-solid'} ${c.confidence === 'low' ? 'border-ov-estimated' : 'border-ov-read'} bg-ov-read/10 group-hover/callout:bg-ov-read/[0.22] group-focus-visible/callout:bg-ov-read/[0.22]`}
            />
            {hover === i && (
              <span
                role="tooltip"
                style={{ position: 'absolute', left: 0, top: hitH + 4 }}
                className="z-popover whitespace-nowrap rounded-[2px] border border-border bg-card px-2 py-1 text-meta text-foreground shadow-md"
              >
                {label}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
