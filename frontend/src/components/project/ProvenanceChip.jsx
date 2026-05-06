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
import AiBadge from './AiBadge';

const SOURCE_META = {
  eksplikacija: {
    label: 'iš eksplikacijos',
    cls: 'bg-blue-500/10 text-blue-300 border-blue-500/30',
    title: 'Skaičius paimtas iš eksplikacijos lentelės. Spausk → matysi eilutę.',
  },
  manual_polygon: {
    label: 'manualu',
    cls: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
    title: 'Skaičius iš tavo apvesto polygono.',
  },
  vision: {
    label: 'iš AI',
    cls: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
    title: 'Skaičius iš AI atpažinimo. Patikrink prieš naudodamas.',
  },
  dimension: {
    label: 'iš dimensijos',
    cls: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30',
    title: 'Skaičius iš brėžinio dimensijos.',
  },
};

export default function ProvenanceChip({ source, onClick }) {
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
        title={meta.title}
        className={`inline-flex items-center px-1.5 py-[1px] rounded border text-[9px] font-medium uppercase tracking-wide ${meta.cls}`}
      >
        {meta.label}
      </button>
      {isAi && <AiBadge label="" />}
    </span>
  );
}
