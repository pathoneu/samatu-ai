/**
 * embedEngine — one place that owns the EmbedPDF engine config (self-hosted
 * wasm + worker) and the plugin registration factory, so the viewer component
 * stays declarative.
 *
 * Task 1 outcome (verified in browser 2026-07-02): worker:true works when the
 * wasmUrl is ABSOLUTE (the worker context cannot resolve a root-relative path).
 * Self-hosted from public/pdfium.wasm — no jsdelivr CDN.
 */
import { createPluginRegistration } from '@embedpdf/core';
import { ViewportPluginPackage } from '@embedpdf/plugin-viewport/react';
import { ScrollPluginPackage } from '@embedpdf/plugin-scroll/react';
import { DocumentManagerPluginPackage } from '@embedpdf/plugin-document-manager/react';
import { RenderPluginPackage } from '@embedpdf/plugin-render/react';
import { ZoomPluginPackage, ZoomMode } from '@embedpdf/plugin-zoom/react';
import { TilingPluginPackage } from '@embedpdf/plugin-tiling/react';
import { InteractionManagerPluginPackage } from '@embedpdf/plugin-interaction-manager/react';
import { ThumbnailPluginPackage } from '@embedpdf/plugin-thumbnail/react';
import { SearchPluginPackage } from '@embedpdf/plugin-search/react';
// The /react print+export packages self-mount their hidden DOM (print iframe,
// download anchor) as EmbedPDF "utilities" — no manual <PrintFrame/> needed.
import { PrintPluginPackage } from '@embedpdf/plugin-print/react';
import { ExportPluginPackage } from '@embedpdf/plugin-export/react';

// Default zoom (founder feedback 2026-07-11: plans opened "far away, hard to
// read"). FitPage computes ONE document zoom that fits the tallest page — the
// portrait A3 cover — so every LANDSCAPE floor plan shrank with it (60% at a
// 1512×982 window, 43% at 1280×720). FitWidth sizes to the widest sheet
// instead: landscape plans fill the pane width (~25-45% larger, readable at
// rest) and the portrait cover is simply taller than the viewport — vertical
// scroll, which this continuous scroller already is.
export const DEFAULT_ZOOM_LEVEL = ZoomMode.FitWidth;

export function engineOptions() {
  return {
    // ABSOLUTE url — resolvable from the worker context (Task 1).
    wasmUrl: new URL('/pdfium.wasm', window.location.origin).href,
    worker: true,
    fontFallback: null, // no external font fetches (self-host guarantee)
  };
}

export function makeViewerPlugins(initialUrl) {
  return [
    createPluginRegistration(DocumentManagerPluginPackage, {
      initialDocuments: [{ url: initialUrl, autoActivate: true }],
    }),
    createPluginRegistration(ViewportPluginPackage),
    createPluginRegistration(ScrollPluginPackage),
    createPluginRegistration(RenderPluginPackage),
    createPluginRegistration(ZoomPluginPackage, { defaultZoomLevel: DEFAULT_ZOOM_LEVEL }),
    createPluginRegistration(TilingPluginPackage),
    createPluginRegistration(InteractionManagerPluginPackage),
    createPluginRegistration(ThumbnailPluginPackage, { width: 120, gap: 8, labelHeight: 16 }),
    createPluginRegistration(SearchPluginPackage),
    createPluginRegistration(PrintPluginPackage),
    // Fallback name only — export prefers the loaded document's own name.
    createPluginRegistration(ExportPluginPackage, { defaultFileName: 'brezinys.pdf' }),
  ];
}
