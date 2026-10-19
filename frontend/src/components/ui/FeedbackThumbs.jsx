/**
 * FeedbackThumbs — 👍 / 👎 plus one optional line (Pathon v3 W5-C, C10). One shape wherever something the
 * program found is rated: pick a thumb (each has its word — „Tinka" / „Netinka" — never the icon alone), write
 * a line if you want, „Siųsti" (or Enter). After sending: „Įrašyta" with „Atšaukti". The caller owns what a
 * rating does (`onSend({up, line})`, `onUndo()`, both may return promises); this owns the steps.
 */

import { useState } from 'react';
import { ThumbsDown, ThumbsUp, Undo2 } from 'lucide-react';

const BTN = 'inline-flex min-h-[36px] items-center gap-1.5 rounded-[2px] border px-3 text-[14px] font-medium '
  + 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50';
const PLAIN = `${BTN} border-border bg-card text-foreground hover:bg-muted`;
const ON = `${BTN} border-accent-2 bg-accent-2/10 text-foreground`;

export default function FeedbackThumbs({
  question, upLabel = 'Tinka', downLabel = 'Netinka', downNote = null, linePlaceholder = 'Pastaba (nebūtina)',
  sentText = 'Įrašyta — ačiū.', onSend, onUndo = null, className = '', testId = 'feedback',
}) {
  const [picked, setPicked] = useState(null);      // null | 'up' | 'down'
  const [line, setLine] = useState('');
  const [phase, setPhase] = useState('ask');       // ask | sending | sent | failed
  const send = async () => {
    if (!picked) return;
    setPhase('sending');
    try {
      await onSend?.({ up: picked === 'up', line });
      setPhase('sent');
    } catch {
      setPhase('failed');
    }
  };
  const undo = async () => {
    setPhase('sending');
    try {
      await onUndo?.();
      setPicked(null);
      setLine('');
      setPhase('ask');
    } catch {
      setPhase('failed');
    }
  };

  if (phase === 'sent') {
    return (
      <div className={`flex flex-wrap items-center gap-2 text-[14px] text-foreground ${className}`} data-testid={`${testId}-sent`}>
        <span>{sentText}</span>
        {onUndo && (
          <button type="button" className={PLAIN} onClick={undo} data-testid={`${testId}-undo`}>
            <Undo2 className="h-4 w-4" aria-hidden="true" /> Atšaukti
          </button>
        )}
      </div>
    );
  }
  return (
    <div className={`text-[14px] text-foreground ${className}`} data-testid={testId}>
      {question && <p className="mb-1.5 font-semibold">{question}</p>}
      <div className="flex flex-wrap items-center gap-1.5">
        <button type="button" className={picked === 'up' ? ON : PLAIN} aria-pressed={picked === 'up'} onClick={() => setPicked('up')} data-testid={`${testId}-up`}>
          <ThumbsUp className="h-4 w-4" aria-hidden="true" /> {upLabel}
        </button>
        <button type="button" className={picked === 'down' ? ON : PLAIN} aria-pressed={picked === 'down'} onClick={() => setPicked('down')} data-testid={`${testId}-down`}>
          <ThumbsDown className="h-4 w-4" aria-hidden="true" /> {downLabel}
        </button>
      </div>
      {picked === 'down' && downNote && <p className="mt-1 text-muted-foreground">{downNote}</p>}
      {picked && (
        <form className="mt-1.5 flex flex-wrap items-center gap-1.5" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <input
            value={line}
            maxLength={200}
            onChange={(e) => setLine(e.target.value)}
            placeholder={linePlaceholder}
            aria-label={linePlaceholder}
            className="h-9 min-w-[12rem] flex-1 rounded-[2px] border border-border bg-background px-2 text-[14px]"
            data-testid={`${testId}-line`}
          />
          <button type="submit" className={PLAIN} disabled={phase === 'sending'} data-testid={`${testId}-send`}>Siųsti</button>
        </form>
      )}
      {phase === 'failed' && <p className="mt-1 text-destructive" role="alert">Įrašyti nepavyko — bandykite dar kartą.</p>}
    </div>
  );
}
