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
    createPluginRegistration(ZoomPluginPackage, { defaultZoomLevel: ZoomMode.FitPage }),
    createPluginRegistration(TilingPluginPackage),
    createPluginRegistration(InteractionManagerPluginPackage),
  ];
}
