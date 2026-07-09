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

// react-pdf worker — align with PlanViewer on the single 4.8.69 worker that
// vite-plugin-static-copy emits to /pdf.worker.mjs. The old import.meta.url
// resolution pulled a second, hoisted pdfjs-dist copy and drifted to a worker
// version (4.10.38) that didn't match react-pdf's API (4.8.69).
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.mjs';

export default function PdfPage({
  file,
  pageNumber,
  onNumPages,
  onPageDims,
  onLoadError,
}) {
  return (
    <Document
      file={file}
      onLoadSuccess={({ numPages }) => onNumPages && onNumPages(numPages)}
      onLoadError={(err) => onLoadError && onLoadError(err)}
      loading={<div className="p-12 text-muted-foreground">Kraunama PDF…</div>}
    >
      <Page
        pageNumber={pageNumber}
        renderTextLayer={false}
        renderAnnotationLayer={false}
        onRenderSuccess={(page) =>
          onPageDims && onPageDims({ width: page.width, height: page.height })
        }
      />
    </Document>
  );
}
