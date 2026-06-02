/**
 * PdfPage — single PDF page renderer.
 *
 * Solely wraps react-pdf's <Document><Page>. Reports rendered dimensions
 * back to the parent via onRenderSuccess so the AnnotationCanvas can
 * size itself to match. Text + annotation layers are disabled for
 * performance (the overlay canvas is the only annotation source we want).
 *
 * Public contract: see docs/viewer-api.md.
 */
import React from 'react';
import { Document, Page, pdfjs } from 'react-pdf';

// react-pdf worker — same wiring as the legacy PdfViewer
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

export default function PdfPage({
  file,
  pageNumber,
  zoom = 1,
  onNumPages,
  onPageDims,
  onLoadError,
}) {
  return (
    <Document
      file={file}
      onLoadSuccess={({ numPages }) => onNumPages && onNumPages(numPages)}
      onLoadError={(err) => onLoadError && onLoadError(err)}
      loading={<div className="p-12 text-neutral-500">Kraunama PDF…</div>}
    >
      <Page
        pageNumber={pageNumber}
        scale={zoom}
        renderTextLayer={false}
        renderAnnotationLayer={false}
        onRenderSuccess={(page) => {
          // react-pdf's `page.width/height` report the UNROTATED PDF page
          // dimensions, which are transposed for landscape pages whose
          // rotation = 90. Read the actual rendered canvas dims instead;
          // those reflect what the user sees and what our overlay must
          // match pixel-for-pixel.
          const canvas = document.querySelector('.react-pdf__Page__canvas');
          let renderedW, renderedH;
          if (canvas) {
            const r = canvas.getBoundingClientRect();
            renderedW = r.width;
            renderedH = r.height;
          } else {
            // Fallback to page-reported (might be transposed on rotated pages)
            renderedW = page.width;
            renderedH = page.height;
          }
          onPageDims && onPageDims({
            width: renderedW / zoom,
            height: renderedH / zoom,
          });
        }}
      />
    </Document>
  );
}
