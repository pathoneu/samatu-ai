/**
 * ConfidenceBadge — Phase C-2 replacement for PolygonReviewBadge.
 *
 * Reflects AREA confidence (whether plotas_m2 is trustworthy) — NOT polygon
 * existence. A room with eksplikacija-derived plotas_m2 but no manual polygon
 * is still 🟡 medium-trust, not (incorrectly) 🟡 "needs trace".
 *
 * Colors:
 *   🟢 tikslus  — multiple sources agree, OR user clicked ✓ patvirtinta
 *   🟡 tikrinti — single source, plausible
 *   🔴 neaišku — sources disagree, OR weak Vision-only
 *
 * No "bbox" or "polygon" word in user-visible text.
 */

import { computeAreaConfidence } from '@/lib/areaConfidence';

const STYLES = {
  high: {
    cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    dot: '🟢',
    label: 'tikslus',
  },
  medium: {
    cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    dot: '🟡',
    label: 'tikrinti',
  },
  low: {
    cls: 'bg-red-500/15 text-red-300 border-red-500/30',
    dot: '🔴',
    label: 'neaišku',
  },
};

export default function ConfidenceBadge({ room, onClick }) {
  const result = computeAreaConfidence(room);
  if (result.confidence === 'unknown') return null;

  const style = STYLES[result.confidence];
  if (!style) return null;

  const sourceList = result.sources
    .map((s) => `${s.label}: ${s.value?.toFixed?.(2) ?? '—'} m²`)
    .join('\n');
  const verifiedLine = result.userVerified
    ? `\nPatvirtinta: ${new Date(room.user_verified_at).toLocaleDateString('lt-LT')}`
    : '';
  const disagreementLine = result.disagreement
    ? '\n⚠ Šaltiniai nesutampa — patikrinti rankiniu būdu.'
    : '';
  const title = `Plotas: ${room.plotas_m2?.toFixed?.(2) ?? '—'} m²\n${sourceList}${verifiedLine}${disagreementLine}`;

  return (
    <button
      onClick={onClick}
      title={title}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-medium ${style.cls}`}
      data-testid={`confidence-badge-${room.nr}`}
      data-confidence={result.confidence}
    >
      <span>{style.dot}</span>
      <span>{style.label}</span>
    </button>
  );
}
