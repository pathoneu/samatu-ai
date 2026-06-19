/**
 * ConfidenceBadge — Phase C-2 replacement for PolygonReviewBadge.
 *
 * Reflects AREA confidence (whether plotas_m2 is trustworthy) — NOT polygon
 * existence. A room with eksplikacija-derived plotas_m2 but no manual polygon
 * is 🟡 medium-trust and offers a one-click ✓ patvirtinta to flip to 🟢.
 *
 * Colors:
 *   🟢 tikslus  — multiple sources agree, OR user clicked ✓ patvirtinta
 *   🟡 tikrinti — single source, plausible
 *   🔴 neaišku — sources disagree, OR weak Vision-only
 */

import { computeAreaConfidence } from '@/lib/areaConfidence';
import { markRoomVerified } from '@/lib/projectStore';
import { Check } from 'lucide-react';

// Light-paper palette (#f6f5f2). The previous dark-theme -300 shades on a /15
// fill rendered washed-out and sub-AA on the light background; -700 text on a
// -50 fill matches the readable WorkRow treatment and the --conf-* tokens.
// (2026-06-19 — repairs the product's hero trust signal.)
const STYLES = {
  high: {
    cls: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    dot: '🟢',
    label: 'tikslus',
  },
  medium: {
    cls: 'bg-amber-50 text-amber-700 border-amber-200',
    dot: '🟡',
    label: 'tikrinti',
  },
  low: {
    cls: 'bg-red-50 text-red-700 border-red-200',
    dot: '🔴',
    label: 'neaišku',
  },
};

export default function ConfidenceBadge({ room, projectId, onClick }) {
  const result = computeAreaConfidence(room);
  if (result.confidence === 'unknown') return null;
  // 2026-05-06: hide badge when confidence is 'high' — trustworthy data
  // doesn't need a "tikslus" pill that just adds visual clutter. The
  // ProvenanceChip ("iš eksplikacijos") is enough signal. We only flag
  // medium / low / disagreeing rooms where the user should look closer.
  if (result.confidence === 'high' && !result.disagreement) return null;

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

  const showVerifyButton =
    result.confidence === 'medium' &&
    !result.userVerified &&
    projectId;

  const handleVerify = (e) => {
    e?.stopPropagation?.();
    if (projectId && room?.nr) {
      markRoomVerified(projectId, room.nr);
    }
  };

  return (
    <span className="inline-flex items-center gap-1">
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
      {showVerifyButton && (
        <button
          onClick={handleVerify}
          title="Patvirtinti, kad skaičius teisingas"
          className="inline-flex items-center gap-0.5 px-1 py-0.5 rounded border text-[9px] font-medium bg-muted/40 text-muted-foreground border-muted hover:bg-emerald-500/15 hover:text-emerald-300 hover:border-emerald-500/30"
          data-testid={`verify-button-${room.nr}`}
        >
          <Check className="w-2.5 h-2.5" />
          <span>patvirtinti</span>
        </button>
      )}
    </span>
  );
}
