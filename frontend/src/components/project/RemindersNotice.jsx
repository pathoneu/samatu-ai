/**
 * RemindersNotice — what an estimator commonly forgets, as ONE notice (Pathon v3 W5-E, E8 + E9).
 *
 * Patikra and the Sąmata both show it, each with the reminders meant for it (lib/reminders.remindersFor):
 * one compact line with the count, the first reminder written out, the rest behind „Rodyti visus (N)" like
 * the other Sąmata notices. Each reminder is a plain sentence that says what to check — never a quantity
 * row, nothing is added to the estimate. A reminder read from the drawing (a fire rating in the text, a long
 * wall, two outlines over each other) has „Rodyti brėžinyje", which frames that place on the drawing.
 * Nothing is hover-only. The list is read once per project; the server saves nothing.
 */
import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronUp, MapPin, Plus } from 'lucide-react';
import { useTranslation } from '@/i18n/react';

import Notice from '@/components/ui/Notice';
import { cleanUserText } from '@/lib/userText';
import { VISIBLE_FIRST, blankRowOf, evidenceTarget, hasBlankRow, remindersFor, remindersWord } from '@/lib/reminders';
import { fetchReminders } from '@/lib/remindersApi';
import { useWorkspaceHost } from './workspaceHost';

export default function RemindersNotice({
  projectId, where, onJumpToPage = null, reloadKey = 0, className = '', rows = null, onAddRow = null,
}) {
  const { t } = useTranslation();
  const host = useWorkspaceHost();
  const [list, setList] = useState([]);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!projectId) return undefined;
    const ctrl = new AbortController();
    fetchReminders(projectId, { signal: ctrl.signal })
      .then((body) => setList(Array.isArray(body?.reminders) ? body.reminders : []))
      .catch(() => { /* no reminders is not an error worth a banner */ });
    return () => ctrl.abort();
  }, [projectId, reloadKey]);

  // E4: a reminder that offers a blank row the sąmata now has is answered — it goes away
  const items = useMemo(
    () => remindersFor(list, where).filter((r) => !(rows && hasBlankRow(rows, blankRowOf(r)))),
    [list, where, rows]);
  if (items.length === 0) return null;

  const reveal = (target) => {
    if (host?.onRevealEvidence) host.onRevealEvidence(target);
    else onJumpToPage?.(target.page);
  };
  const canReveal = Boolean(host?.onRevealEvidence || onJumpToPage);
  const shown = expanded ? items : items.slice(0, VISIBLE_FIRST);
  const rest = items.length - VISIBLE_FIRST;
  const tone = items.some((r) => r.tone === 'warning') ? 'warning' : 'info';

  return (
    <Notice
      tone={tone}
      className={className}
      title={t('project.reminders.title', { count: items.length, word: remindersWord(items.length) })}
      data-testid={`reminders-${where}`}
      action={rest > 0 ? (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="inline-flex min-h-[32px] items-center gap-1 rounded border border-border bg-card px-2.5 text-ui font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          data-testid="reminders-toggle"
        >
          {expanded ? <ChevronUp className="h-4 w-4" aria-hidden="true" /> : <ChevronDown className="h-4 w-4" aria-hidden="true" />}
          {expanded ? t('project.reminders.collapse') : t('project.reminders.showAll', { count: items.length })}
        </button>
      ) : null}
    >
      <p className="text-muted-foreground">{t('project.reminders.sub')}</p>
      <ul className="space-y-1.5">
        {shown.map((r) => {
          const target = canReveal ? evidenceTarget(r) : null;
          return (
            <li key={r.id} className="flex items-start gap-2" data-reminder={r.kind}>
              <span className="shrink-0 text-muted-foreground" aria-hidden="true">·</span>
              <div className="min-w-0 flex-1">
                <span className="text-foreground">{cleanUserText(r.sentence)}</span>
                {onAddRow && blankRowOf(r) && (
                  <button
                    type="button"
                    onClick={() => onAddRow(blankRowOf(r))}
                    className="ml-2 inline-flex items-center gap-1 underline hover:no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    style={{ color: 'hsl(var(--accent-2))' }}
                    data-testid="reminder-add-row"
                  >
                    <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                    {t('project.reminders.addBlankRow')}
                  </button>
                )}
                {target && (
                  <button
                    type="button"
                    onClick={() => reveal(target)}
                    className="ml-2 inline-flex items-center gap-1 underline hover:no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    style={{ color: 'hsl(var(--accent-2))' }}
                  >
                    <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                    {t('project.reminders.reveal', { page: target.page })}
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </Notice>
  );
}
