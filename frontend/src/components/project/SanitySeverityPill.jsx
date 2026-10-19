/**
 * SanitySeverityPill — "2 įspėjimai · 5 pastabos" in the project top bar.
 *
 * The sanity banner lives on the Kiekiai tab, but a project LANDS on Brėžinys
 * (InteriorProject.jsx: useState(() => 'brezinys')). A first-time user — the
 * exact person the §6 cross-checks exist to protect — therefore never saw
 * them. This pill sits in ProjectTopBar, which renders above the tab bar on
 * every tab, and jumps to the banner when clicked.
 *
 * Deliberately tiny: one line of text, a dot, and a count. The viewer is not
 * redesigned around it.
 */

import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertCircle, AlertTriangle, Info } from 'lucide-react';

import { summarizeSanity, warningKey } from '../../lib/sanitySeverity';
import {
  loadDismissed,
  subscribeDismissals,
  withoutDismissed,
} from '../../lib/sanityDismissals';

export default function SanitySeverityPill({ sanity, onOpen }) {
  const { t } = useTranslation();
  // Honour the same dismissals the banner does — a count the user can never
  // clear is one they learn to ignore, which defeats the point of the pill.
  const [dismissed, setDismissed] = useState(loadDismissed);
  useEffect(() => subscribeDismissals(() => setDismissed(loadDismissed())), []);

  const counts = useMemo(
    () => summarizeSanity({
      warnings: withoutDismissed(sanity?.warnings, dismissed, warningKey),
    }),
    [sanity, dismissed],
  );
  if (counts.total === 0) return null;

  // Loudest tier present decides the colour and the icon.
  const tone = counts.high > 0
    ? 'var(--conf-low)'
    : (counts.med > 0 ? 'var(--conf-med)' : 'var(--muted-foreground)');
  const Icon = counts.high > 0
    ? AlertCircle
    : (counts.med > 0 ? AlertTriangle : Info);

  return (
    <button
      type="button"
      onClick={onOpen}
      title={t('project.sanity.pillTitle')}
      className="flex items-center gap-1.5 rounded transition-colors shrink-0 hover:brightness-95"
      style={{
        height: 24,
        padding: '0 8px',
        fontSize: 12,
        fontWeight: 500,
        // the words in ink, the tone on the frame, tint and icon (the Notice rule): amber words on the
        // amber tint were 4,1:1 on the parchment bar (ui-probe, v3 W6-A)
        color: 'hsl(var(--foreground))',
        border: `1px solid hsl(${tone} / 0.4)`,
        background: `hsl(${tone} / 0.08)`,
      }}
    >
      <Icon className="w-3 h-3 shrink-0" style={{ color: `hsl(${tone})` }} />
      <span className="whitespace-nowrap">
        {t('project.sanity.pillWarnings', { count: counts.warnings })}
        {' · '}
        {t('project.sanity.pillNotes', { count: counts.notes })}
      </span>
    </button>
  );
}
