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
        renderTextLayer={false}
        renderAnnotationLayer={false}
        onRenderSuccess={(page) =>
          onPageDims && onPageDims({ width: page.width, height: page.height })
        }
      />
    </Document>
  );
}
