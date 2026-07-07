import React from 'react';
import { Check, Pencil, Sparkles } from 'lucide-react';

/**
 * VerifiedBadge — shows the provenance of a single quantity line:
 *   - ai       → small sparkles icon (orange)
 *   - rule     → no badge (default rule-based output)
 *   - user     → pencil icon (blue) — user edited
 *   - verified → check icon (green) — user pressed Patikrinta
 *
 * Pairs with the correction flow: editing a line marks source → 'user', and
 * confirming it marks source → 'verified', which triggers the green check here.
 */
export function VerifiedBadge({ source }) {
  if (source === 'verified') {
    return (
      <span
        className="inline-flex items-center gap-1 text-emerald-700 text-xs font-medium"
        title="Patikrinta — vartotojas patvirtino šią reikšmę"
      >
        <Check className="w-3.5 h-3.5" />
        Patikrinta
      </span>
    );
  }
  if (source === 'user') {
    return (
      <span
        className="inline-flex items-center gap-1 text-blue-700 text-xs font-medium"
        title="Vartotojo redaguota"
      >
        <Pencil className="w-3.5 h-3.5" />
        Redaguota
      </span>
    );
  }
  if (source === 'ai') {
    return (
      <span
        className="inline-flex items-center gap-1 text-amber-700 text-xs"
        title="AI siūloma — patikrinkite prieš naudodami"
      >
        <Sparkles className="w-3.5 h-3.5" />
        AI
      </span>
    );
  }
  return null;
}

export default VerifiedBadge;
