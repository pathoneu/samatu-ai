/**
 * NotesList — the „Pastaba" pins listed with the measurements (Pathon v3 W5-C, C11 / #179): the button that
 * arms the pin tool on the drawing, and every note with its number, its text and its sheet — a click jumps
 * to the sheet. The pins themselves are drawn by viewer/DrawingNoteLayer.
 */

import { StickyNote } from 'lucide-react';

import { noteNumbers, notesOf, setNoteToolArmed } from '@/lib/drawingNotes';
import { useNoteToolArmed } from '@/components/viewer/DrawingNoteLayer';

export default function NotesList({ project, onJumpToPage = null }) {
  const armed = useNoteToolArmed();
  const notes = notesOf(project?.measurements);
  const numbers = noteNumbers(project?.measurements);
  return (
    <div className="border-b border-border/60" data-testid="notes-list">
      <div className="flex items-center gap-2 px-3 py-2 text-ui">
        <StickyNote className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className="flex-1 font-medium text-foreground">Pastabos brėžinyje{notes.length ? ` (${notes.length})` : ''}</span>
        <button
          type="button"
          onClick={() => setNoteToolArmed(!armed)}
          aria-pressed={armed}
          className={`inline-flex min-h-[32px] items-center rounded-[2px] border px-2.5 font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${armed
            ? 'border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2)/0.1)] text-foreground'
            : 'border-border bg-card text-foreground hover:bg-muted'}`}
          data-testid="note-arm"
        >
          {armed ? 'Baigti dėti pastabas' : '+ Pastaba brėžinyje'}
        </button>
      </div>
      {armed && (
        <p className="px-3 pb-2 text-ui text-muted-foreground">Spustelėkite brėžinyje, kur dėti pastabą, ir įrašykite jos tekstą.</p>
      )}
      {notes.length > 0 && (
        <ul>
          {notes.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                onClick={onJumpToPage ? () => onJumpToPage(n.page) : undefined}
                className="flex w-full items-start gap-2 border-t border-border/50 px-3 py-2 text-left text-ui hover:bg-muted/40"
                title={onJumpToPage ? `Rodyti brėžinyje (psl. ${n.page})` : undefined}
                data-testid="notes-list-row"
              >
                <span className="font-mono font-semibold text-foreground">{numbers.get(n.id)}</span>
                <span className="min-w-0 flex-1 whitespace-pre-wrap text-foreground">{n.text}</span>
                <span className="shrink-0 text-muted-foreground">psl. {n.page}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
