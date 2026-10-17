/**
 * RevisionOverlayLayer — a later edition of the drawing laid over this sheet (togal-v2 W10).
 *
 * The server paints the comparison in this sheet's DISPLAY frame (api/pdf_revisions.py: lines only in the
 * new edition evergreen, only in the old one clay — or the whole new edition), so this layer is one
 * transparent picture stretched over the page, like DrawingGeometryLayer's SVG: outside PageOverlayHost's
 * rotation wrapper, nothing rotated here; pageRotation only says which side of the box is the width when
 * the sharpness tier is chosen. Pointer-transparent: clicks go through to zones and measure tools.
 */
import { useState } from 'react';
import { displayWidthPt, dpiTier, overlayUrl } from '@/lib/pdfRevisions';

export default function RevisionOverlayLayer({ projectId, page, overlay, renderedSize, pageSizePt, pageRotation }) {
  const { width, height } = renderedSize || {};
  const [failed, setFailed] = useState(null);
  const match = overlay?.record?.pagal_sena?.[String(page)];
  if (!projectId || !overlay?.rid || !match || !width || !height) return null;
  const dpi = dpiTier(width, displayWidthPt(pageSizePt, pageRotation));
  const src = overlayUrl(projectId, overlay.rid, page, overlay.mode, dpi);
  if (failed === src) return null;
  return (
    <img
      src={src}
      alt=""
      draggable={false}
      onError={() => setFailed(src)}
      data-revision-overlay={overlay.mode}
      style={{
        position: 'absolute', inset: 0, width, height, pointerEvents: 'none',
        opacity: Math.max(0, Math.min(1, Number(overlay.opacity) || 0)),
        imageRendering: 'auto',
      }}
    />
  );
}
