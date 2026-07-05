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
 * Phase C-4-bis: AI-adjacent sources (eksplikacija auto-reader, Vision)
 * also render a small ✨ AI badge so the user perceives the tool's
 * intelligence, à la Kreo's takeoff UI.
 *
 * No "bbox" or "polygon" jargon in any visible string.
 */
import { useTranslation } from 'react-i18next';
import AiBadge from './AiBadge';

// Dark graphite palette (2026-07-05): -300 text on a /15 fill of the same hue
// reads clearly and passes AA on graphite; the previous -700-on-(-50) treatment
// (light-paper era) rendered as bright pastel pills on the dark background.
// label/title resolve against i18n at render (project.provenance.*).
const SOURCE_META = {
  eksplikacija: {
    labelKey: 'project.provenance.eksplikacijaLabel',
    cls: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
    titleKey: 'project.provenance.eksplikacijaTitle',
  },
  manual_polygon: {
    labelKey: 'project.provenance.manualLabel',
    cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    titleKey: 'project.provenance.manualTitle',
  },
  vision: {
    labelKey: 'project.provenance.visionLabel',
    cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    titleKey: 'project.provenance.visionTitle',
  },
  dimension: {
    labelKey: 'project.provenance.dimensionLabel',
    cls: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    titleKey: 'project.provenance.dimensionTitle',
  },
};

export default function ProvenanceChip({ source, onClick }) {
  const { t } = useTranslation();
  const meta = SOURCE_META[source];
  if (!meta) return null;
  // 2026-05-06: ✨ badge ONLY for direct Vision output. Eksplikacija is
  // deterministic pdfplumber extraction (NOT AI inference), so it does not
  // deserve the AI sparkle. Showing it on eksplikacija rooms was creating
  // visual clutter and misrepresenting the data flow.
  const isAi = source === 'vision';
  return (
    <span className="inline-flex items-center gap-1" data-testid={`provenance-chip-${source}`}>
      <button
        onClick={onClick}
        title={t(meta.titleKey)}
        className={`inline-flex items-center px-1.5 py-[1px] rounded border text-[9px] font-medium uppercase tracking-wide ${meta.cls}`}
      >
        {t(meta.labelKey)}
      </button>
      {isAi && <AiBadge label="" />}
    </span>
  );
}
