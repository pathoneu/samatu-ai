/**
 * PdfMultiPage — render ALL pages of a PDF stacked vertically.
 *
 * Replaces the single-page <PdfPage> for takeoff use: contractors
 * scroll the whole drawing as one continuous canvas instead of
 * paginating.
 *
 * Reports a `pagesLayout` array to the parent:
 *   [{pageNum, width, height, offsetY}, ...]
 * which the annotation overlay uses to map canvas-y back to
 * (pageNum, y_pct).
 *
 * Per-page gap of PAGE_GAP_PX so adjacent pages are visually separated.
 *
 * Virtualization (NOT in this version): bacveviciaus's 65 pages will
 * render every page; that's a TODO follow-up using Intersection
 * Observer or react-virtualized. For Beržų (17 pages) it's fine.
 */
import React, { useEffect, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

export const PAGE_GAP_PX = 16;

export default function PdfMultiPage({
  file,
  zoom = 1,
  onNumPages,
  onPagesLayout,
  onLoadError,
}) {
  const [numPages, setNumPages] = useState(0);
  // Per-page dimensions reported by each <Page> via onRenderSuccess.
  // Keyed by 1-based page number.
  const [perPageDims, setPerPageDims] = useState({});

  const reportPageDims = (pageNum, w, h) => {
    setPerPageDims((prev) => {
      if (prev[pageNum] && prev[pageNum].width === w && prev[pageNum].height === h) {
        return prev;
      }
      return { ...prev, [pageNum]: { width: w, height: h } };
    });
  };

  // Whenever per-page dims are filled in, compute the stacked layout
  // and report it upward.
  useEffect(() => {
    if (!numPages || Object.keys(perPageDims).length < numPages) return;
    const layout = [];
    let y = 0;
    let maxWidth = 0;
    for (let i = 1; i <= numPages; i++) {
      const dims = perPageDims[i];
      if (!dims) {
        // Missing dim — skip the whole layout publish until all pages render
        return;
      }
      layout.push({
        pageNum: i,
        width: dims.width,
        height: dims.height,
        offsetY: y,
      });
      y += dims.height + PAGE_GAP_PX;
      if (dims.width > maxWidth) maxWidth = dims.width;
    }
    onPagesLayout && onPagesLayout({
      pages: layout,
      totalWidth: maxWidth,
      totalHeight: y - PAGE_GAP_PX,  // no trailing gap
    });
  }, [numPages, perPageDims, onPagesLayout]);

  return (
    <Document
      file={file}
      onLoadSuccess={({ numPages: n }) => {
        setNumPages(n);
        onNumPages && onNumPages(n);
      }}
      onLoadError={(err) => onLoadError && onLoadError(err)}
      loading={<div className="p-12 text-neutral-500">Kraunama PDF…</div>}
    >
      {/* items-start (not items-center) so narrower pages stay at x=0 in the
          stacked layout. Otherwise the canvas overlay would have to know each
          page's horizontal centering offset to align polygons correctly. */}
      <div className="flex flex-col items-start">
        {Array.from({ length: numPages }, (_, i) => {
          const pageNum = i + 1;
          return (
            <div
              key={pageNum}
              data-testid={`pdf-page-${pageNum}`}
              data-page-num={pageNum}
              style={{ marginBottom: PAGE_GAP_PX }}
              className="bg-white shadow"
            >
              <Page
                pageNumber={pageNum}
                scale={zoom}
                renderTextLayer={false}
                renderAnnotationLayer={false}
                onRenderSuccess={() => {
                  // Read the rendered canvas dimensions directly —
                  // react-pdf's page.width/height transposes on rotated pages
                  // (we hit this in commit 8fcf7fb).
                  const el = document.querySelector(
                    `[data-page-num="${pageNum}"] .react-pdf__Page__canvas`,
                  );
                  if (el) {
                    const r = el.getBoundingClientRect();
                    reportPageDims(pageNum, r.width / zoom, r.height / zoom);
                  }
                }}
              />
            </div>
          );
        })}
      </div>
    </Document>
  );
}
