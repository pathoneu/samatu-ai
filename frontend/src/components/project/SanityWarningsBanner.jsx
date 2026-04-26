/**
 * SanityWarningsBanner — rodo LT specifikos warnings vartotojui.
 *
 * Backend grąžina `lt_sanity.warnings[]` — kiekvienas su level (WARNING/INFO/ERROR)
 * ir message. Vartotojas mato kuriuose kambariuose AI gali būti suklydęs.
 *
 * Tikslas: pagal skill F.3 ir B.1 — vartotojas mato kur tikrinti, nei
 * tiesiog patikėti AI rezultatu.
 */

import { useState } from 'react';
import { AlertTriangle, AlertCircle, Info, ChevronDown, ChevronUp, X } from 'lucide-react';

const LEVEL_META = {
  ERROR:   { icon: AlertCircle,   color: 'text-red-700 bg-red-50 border-red-200 dark:bg-red-950/20' },
  WARNING: { icon: AlertTriangle, color: 'text-amber-800 bg-amber-50 border-amber-200 dark:bg-amber-950/20' },
  INFO:    { icon: Info,          color: 'text-blue-700 bg-blue-50 border-blue-200 dark:bg-blue-950/20' },
};

export default function SanityWarningsBanner({ sanity }) {
  const [expanded, setExpanded] = useState(false);

  if (!sanity || !sanity.warnings || sanity.warnings.length === 0) {
    return null;
  }

  const warnings = sanity.warnings;
  const summary = sanity.summary || {};
  const totalWarnings = (summary.warnings || 0) + (summary.errors || 0);

  // Default'iškai rodom TIK warnings ir errors. Info'us — slepiam į expand.
  const visible = expanded
    ? warnings
    : warnings.filter(w => w.level !== 'INFO');

  if (visible.length === 0 && !expanded) {
    return null;
  }

  // Pasirenkam svarbiausią level'ą banner'iui
  const topLevel = warnings.some(w => w.level === 'ERROR') ? 'ERROR'
                 : warnings.some(w => w.level === 'WARNING') ? 'WARNING'
                 : 'INFO';
  const meta = LEVEL_META[topLevel];
  const Icon = meta.icon;

  return (
    <div className={`border rounded-lg p-3 ${meta.color}`}>
      <div className="flex items-start gap-2.5">
        <Icon className="w-4 h-4 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-sm font-semibold">
              AI patikrinimas: aptikta {totalWarnings} {totalWarnings === 1 ? 'pastaba' : 'pastabos'}
            </span>
            <span className="text-xs opacity-75">
              · {summary.rooms_count} patalpų, {summary.total_area_m2} m²
            </span>
          </div>

          <ul className="space-y-1">
            {visible.slice(0, expanded ? 50 : 5).map((w, i) => (
              <li key={i} className="text-xs flex items-start gap-1.5">
                <span className="opacity-60 shrink-0 mt-0.5">·</span>
                <span>{w.message}</span>
              </li>
            ))}
          </ul>

          {warnings.length > 5 && (
            <button
              onClick={() => setExpanded(v => !v)}
              className="mt-2 text-xs font-medium underline-offset-2 hover:underline flex items-center gap-1"
            >
              {expanded
                ? <><ChevronUp className="w-3 h-3" /> Suskleisti</>
                : <><ChevronDown className="w-3 h-3" /> Rodyti visus ({warnings.length})</>
              }
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
