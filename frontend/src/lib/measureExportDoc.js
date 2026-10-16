import { effectivePageScales } from './pageScales.js';

/**
 * buildMeasureExportDoc — the exact document the Matavimai CSV/JSON export ships.
 *
 * 2026-07-27 audit: the export used `project.pageScalesDurable` alone, while the
 * on-screen Matavimai list merges the auto-calibration derived from traced rooms
 * on top of it. On a page that was never calibrated by hand (the normal case —
 * auto-calibration is the whole point) every exported length came out as
 * "nekalibruota" / 0,00 even though the panel showed real metres. Same merge
 * order as the viewer and the panel: auto first, user calibration wins.
 */
export function buildMeasureExportDoc(project) {
  return {
    measurements: project?.measurements || [],
    // 2026-10-16: the lane's scales too (lib/pageScales) — the viewer measured in metres on objektas_h's
    // lane-scaled sheets while the export said „nekalibruota".
    measureScales: effectivePageScales(project),
    countTypes: project?.countTypes || [],
  };
}

export default buildMeasureExportDoc;
