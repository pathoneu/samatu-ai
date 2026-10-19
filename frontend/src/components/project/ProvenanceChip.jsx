/**
 * ProvenanceChip — small "iš kur tai?" pill next to a kiekiai number.
 *
 * Click → onClick callback (typically navigates the PDF to the source +
 * flashes a halo over the source row/dimension).
 *
 * Phase C-2 sources:
 *   - 'eksplikacija' → "iš eksplikacijos" (eksplikacija text)
 *   - 'manual_polygon' → "manualu" (user-traced polygon)
 *   - 'vision' → "iš AI" (Vision-only, low trust)
 *   - 'dimension' → "iš dimensijos" (placeholder for future)
 *
 * v3 W6-A: the sparkle „AI" badge after the Vision label is gone (a toy trope, 8 px, empty
 * label) — the label and its title already say the number came from the drawing's picture.
 *
 * No "bbox" or "polygon" jargon in any visible string.
 */
import { useTranslation } from '@/i18n/react';

// v3 W1-C: a quiet 12 px text link in sentence case — it was a 9 px uppercase pill, blue-300 on
// blue-500/15 (a dark-theme leftover: 1,47:1 on parchment, 11 times per screen). The words say where
// the number came from; the colour only marks a link: the drawing's table or text = the evergreen
// link colour, his own outline = ink, the drawing's picture (worth a look) = the estimate amber.
// label/title resolve against i18n at render (project.provenance.*).
const SOURCE_META = {
  eksplikacija: {
    labelKey: 'project.provenance.eksplikacijaLabel',
    cls: 'text-accent-2',
    titleKey: 'project.provenance.eksplikacijaTitle',
  },
  manual_polygon: {
    labelKey: 'project.provenance.manualLabel',
    cls: 'text-foreground',
    titleKey: 'project.provenance.manualTitle',
  },
  vision: {
    labelKey: 'project.provenance.visionLabel',
    cls: 'text-ov-estimated',
    titleKey: 'project.provenance.visionTitle',
  },
  // 2026-09-06: the designer's own room area written on the plan („37.86 m²"
  // inside the room), read from the PDF text layer — deterministic, exact.
  plano_uzrasas: {
    labelKey: 'project.provenance.planoUzrasasLabel',
    cls: 'text-accent-2',
    titleKey: 'project.provenance.planoUzrasasTitle',
  },
  dimension: {
    labelKey: 'project.provenance.dimensionLabel',
    cls: 'text-accent-2',
    titleKey: 'project.provenance.dimensionTitle',
  },
};

export default function ProvenanceChip({ source, onClick }) {
  const { t } = useTranslation();
  const meta = SOURCE_META[source];
  if (!meta) return null;
  return (
    <span className="inline-flex items-center gap-1" data-testid={`provenance-chip-${source}`}>
      <button
        onClick={onClick}
        title={t(meta.titleKey)}
        className={`inline-flex items-center whitespace-nowrap text-meta font-medium underline decoration-dotted underline-offset-2 hover:decoration-solid ${meta.cls}`}
      >
        {t(meta.labelKey)}
      </button>
    </span>
  );
}
