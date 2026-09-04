/**
 * PreflightCard — what the five-second look at the PDF found, before the spend.
 *
 * ONE card, no new page, no modal. It answers the three things a contractor
 * cannot see from a filename: how many pages, roughly how long the analysis
 * will take, and whether this file looks like something we can measure at all.
 *
 * The verdict line is deliberately hedged ("Atrodo, kad…") because it is a
 * heuristic read of the PDF's text layer, not an analysis — see
 * backend/extractor/preflight.py. The user can always continue; only a
 * page count past the pipeline's limit actually blocks, and that one is a
 * fact, not a guess.
 */

import { useTranslation } from 'react-i18next';
import { FileSearch, AlertTriangle, Ban, CheckCircle2, Clock, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { verdictKey } from '@/lib/preflight';

const TONE = {
  ok:      { icon: CheckCircle2,  border: 'border-border',              accent: 'text-[hsl(var(--conf-high))]' },
  neutral: { icon: FileSearch,    border: 'border-border',              accent: 'text-muted-foreground' },
  caution: { icon: AlertTriangle, border: 'border-[hsl(var(--conf-med))]/45', accent: 'text-[hsl(var(--conf-med))]' },
  blocked: { icon: Ban,           border: 'border-destructive/40',      accent: 'text-destructive' },
};

export default function PreflightCard({
  card, loading = false, onContinue, onPickAnother, onContinueAnyway,
}) {
  const { t } = useTranslation();

  if (loading) {
    return (
      <div className="mt-2 flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-3 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
        {t('newProject.preflight.checking')}
      </div>
    );
  }
  if (!card) return null;

  const tone = TONE[card.tone] || TONE.neutral;
  const Icon = tone.icon;

  return (
    <div
      role="status"
      className={`mt-2 rounded-lg border ${tone.border} bg-card p-4`}
    >
      <div className="flex items-start gap-3">
        <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${tone.accent}`} aria-hidden="true" />
        <div className="min-w-0 flex-1">
          {/* The diagnosis line, in the shape the design asks for: „17 lapų ·
              interjero brėžinių ~9 psl. · skaičiuosime apie 15–25 min."
              Only facts the probe actually measured go on this line. It does
              NOT say „yra kambarių lentelė" — the preflight counts table-like
              pages but cannot tell an eksplikacija from any other table, and a
              confident claim about the room table is exactly the claim a
              contractor would rely on. */}
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-foreground" style={{ fontSize: 15 }}>
            <span className="font-medium tabular-nums">
              {t('newProject.preflight.pages', { n: card.pageCount })}
            </span>
            {card.interiorPages > 0 && (
              <>
                <span aria-hidden className="text-muted-foreground">·</span>
                <span className="text-muted-foreground">
                  {t('newProject.preflight.interiorPages', { n: card.interiorPages })}
                </span>
              </>
            )}
            {card.estMinutes && (
              <>
                <span aria-hidden className="text-muted-foreground">·</span>
                <span className="inline-flex items-center gap-1 text-muted-foreground">
                  <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                  {t('newProject.preflight.duration', { value: card.estMinutes })}
                </span>
              </>
            )}
          </div>

          {/* The guess. */}
          <p className="mt-1.5 text-foreground" style={{ fontSize: 15 }}>{t(verdictKey(card.verdict))}</p>

          {card.reason && (
            <p className="mt-1.5 text-sm font-medium text-destructive">{card.reason}</p>
          )}

          {card.warnings.length > 0 && (
            <ul className="mt-1.5 space-y-1">
              {card.warnings.map((w) => (
                <li key={w} className="text-xs text-muted-foreground">— {w}</li>
              ))}
            </ul>
          )}

          {/* Never let the card be mistaken for the analysis itself. */}
          <p className="mt-2 text-[11px] text-muted-foreground">
            {t('newProject.preflight.disclaimer')}
          </p>

          {card.needsDecision && (
            <div className="mt-3 flex flex-wrap gap-2">
              {!card.blocked && (
                <Button
                  size="sm"
                  onClick={onContinue}
                  title={t('newProject.preflight.continueTitle')}
                  className="bg-primary text-primary-foreground hover:bg-primary/90"
                >
                  {t('newProject.preflight.continue')}
                </Button>
              )}
              <Button
                size="sm"
                variant="outline"
                onClick={onPickAnother}
                title={t('newProject.preflight.pickAnotherTitle')}
              >
                {t('newProject.preflight.pickAnother')}
              </Button>
              {/* A block must never be a dead end. Splitting the PDF is the
                  RIGHT answer and stays the primary one — but a contractor
                  whose interior sheets happen to sit inside the first 100
                  pages used to be refused outright, with no way through and
                  nobody to ask. He is told exactly what he gives up; the
                  decision is his. (Before 2026-08-23 this file uploaded fine
                  and the backend simply capped at 100 pages.) */}
              {card.blocked && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={onContinueAnyway}
                  title={t('newProject.preflight.overrideBlockTitle')}
                  className="text-muted-foreground hover:text-foreground"
                >
                  {t('newProject.preflight.overrideBlock')}
                </Button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
