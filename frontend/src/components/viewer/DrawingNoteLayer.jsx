/**
 * DrawingNoteLayer — „Pastaba" pins on one sheet (Pathon v3 W5-C, C11 / #179, #180). Mounted per page by
 * PageOverlayHost, page-sized, above the measurements.
 *
 *   at rest   each note is a pin with its number and a short label beside it (always visible, never only on
 *             hover); a click opens it: the whole text, „Keisti", „Ištrinti" (with „Atšaukti" in the toast)
 *   armed     („+ Pastaba brėžinyje" in Matavimai, lib/drawingNotes store) the layer owns the click: one click
 *             puts a pin and opens its text field — Enter saves, Esc drops it; the sentence beside the pointer
 *             says what to do. Esc with nothing open leaves the tool.
 *
 * Notes are measurements of kind `note` (the viewer's save path and history): `onCommit(note)` adds one,
 * `onDelete(id)` removes one; a text change is delete + add under the same id.
 */

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { StickyNote, X } from 'lucide-react';

import {
  makeNote, noteLabel, noteNumbers, notesOf, noteToolArmed, setNoteToolArmed, subscribeNoteTool,
} from '@/lib/drawingNotes';

const BTN = 'inline-flex min-h-[32px] items-center gap-1 rounded-[2px] border border-border bg-card px-2 text-[14px] font-medium text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

export function useNoteToolArmed() {
  const [armed, setArmed] = useState(noteToolArmed());
  useEffect(() => subscribeNoteTool(setArmed), []);
  return armed;
}

function NoteEditor({ initial = '', onSave, onCancel }) {
  const [text, setText] = useState(initial);
  return (
    <form
      className="w-64 rounded-[2px] border border-border bg-card p-2 shadow-md"
      onSubmit={(e) => { e.preventDefault(); if (text.trim()) onSave(text); }}
      onPointerDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      data-testid="note-editor"
    >
      <label className="mb-1 block text-[14px] font-semibold" htmlFor="note-text">Pastaba</label>
      <textarea
        id="note-text"
        autoFocus
        rows={3}
        maxLength={500}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (text.trim()) onSave(text); }
          if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); onCancel(); }
        }}
        className="w-full resize-none rounded-[2px] border border-border bg-background p-1.5 text-[14px]"
        data-testid="note-text"
      />
      <p className="mt-1 text-[14px] text-muted-foreground">Enter — išsaugoti · Esc — atšaukti</p>
      <div className="mt-1.5 flex gap-1.5">
        <button type="submit" className={`${BTN} border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2))] text-white`} disabled={!text.trim()} data-testid="note-save">Išsaugoti</button>
        <button type="button" className={BTN} onClick={onCancel}>Atšaukti</button>
      </div>
    </form>
  );
}

export default function DrawingNoteLayer({ page, measurements = [], adapter, onCommit, onDelete }) {
  const armed = useNoteToolArmed();
  const [draft, setDraft] = useState(null);       // {x, y} PDF points of a pin not yet saved
  const [openId, setOpenId] = useState(null);
  const [editing, setEditing] = useState(false);
  const [pointer, setPointer] = useState(null);   // where the sentence beside the cursor stands
  const notes = notesOf(measurements, page);
  const numbers = noteNumbers(measurements);

  // Esc with nothing open leaves the tool (an open field takes its own Esc first)
  useEffect(() => {
    if (!armed) return undefined;
    const onKey = (e) => {
      if (e.key !== 'Escape' || draft || editing) return;
      setNoteToolArmed(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [armed, draft, editing]);
  useEffect(() => { if (!armed) setDraft(null); }, [armed]);

  if (!adapter) return null;
  const at = (p) => adapter.toViewport(p);

  const save = (text) => {
    if (!draft) return;
    const note = makeNote({ page, x: draft.x, y: draft.y, text });
    onCommit?.(note);
    setDraft(null);
    toast.success('Pastaba įrašyta', {
      description: 'Ji matoma brėžinyje, sąraše „Matavimai" ir „PDF su žymėjimais".',
      duration: 6000,
      action: { label: 'Atšaukti', onClick: () => onDelete?.(note.id) },
    });
  };
  const change = (note, text) => {
    onDelete?.(note.id);
    onCommit?.({ ...note, text: String(text).trim().slice(0, 500) });
    setEditing(false);
  };
  const remove = (note) => {
    onDelete?.(note.id);
    setOpenId(null);
    toast('Pastaba ištrinta', { duration: 6000, action: { label: 'Atšaukti', onClick: () => onCommit?.(note) } });
  };

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} data-testid="note-layer">
      {/* armed: the whole sheet takes the click that puts a pin */}
      {armed && !draft && (
        <div
          style={{ position: 'absolute', inset: 0, pointerEvents: 'auto', cursor: 'crosshair' }}
          onPointerDown={(e) => e.stopPropagation()}
          onPointerMove={(e) => { const r = e.currentTarget.getBoundingClientRect(); setPointer({ x: e.clientX - r.left, y: e.clientY - r.top }); }}
          onPointerLeave={() => setPointer(null)}
          onClick={(e) => {
            e.stopPropagation();
            const r = e.currentTarget.getBoundingClientRect();
            const p = adapter.toPdf({ x: e.clientX - r.left, y: e.clientY - r.top });
            setDraft(p);
            setOpenId(null);
          }}
          data-testid="note-capture"
        >
          {pointer && (
            <span
              className="pointer-events-none absolute whitespace-nowrap rounded-[2px] border border-border bg-card px-2 py-0.5 text-[14px] text-foreground shadow-sm"
              style={{ left: pointer.x + 14, top: pointer.y + 14 }}
            >
              Spustelėkite, kur dėti pastabą · Esc — baigti
            </span>
          )}
        </div>
      )}

      {notes.map((n) => {
        const p = at(n.points[0]);
        const open = openId === n.id;
        return (
          <div key={n.id} style={{ position: 'absolute', left: p.x, top: p.y, pointerEvents: 'auto' }} data-testid="note-pin" data-note-id={n.id}>
            <button
              type="button"
              onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => { e.stopPropagation(); setOpenId(open ? null : n.id); setEditing(false); }}
              className="-translate-x-1/2 -translate-y-full inline-flex items-center gap-1 rounded-[2px] border border-[hsl(var(--ink-2))] bg-card px-1.5 py-0.5 text-[14px] font-semibold text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-expanded={open}
              aria-label={`Pastaba ${numbers.get(n.id) || ''}: ${n.text}`}
            >
              <StickyNote className="h-4 w-4" aria-hidden="true" />
              {numbers.get(n.id)}
              <span className="max-w-[14rem] truncate font-normal">{noteLabel(n.text, 28)}</span>
            </button>
            {open && (
              <div className="absolute left-0 top-1 z-10" onPointerDown={(e) => e.stopPropagation()} onClick={(e) => e.stopPropagation()}>
                {editing ? (
                  <NoteEditor initial={n.text} onSave={(t) => change(n, t)} onCancel={() => setEditing(false)} />
                ) : (
                  <div className="w-64 rounded-[2px] border border-border bg-card p-2 shadow-md" data-testid="note-open">
                    <div className="flex items-start gap-2">
                      <p className="flex-1 whitespace-pre-wrap text-[14px] text-foreground">{n.text}</p>
                      <button type="button" className="text-muted-foreground hover:text-foreground" aria-label="Uždaryti" onClick={() => setOpenId(null)}>
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                    <div className="mt-2 flex gap-1.5">
                      <button type="button" className={BTN} onClick={() => setEditing(true)}>Keisti</button>
                      <button type="button" className={BTN} onClick={() => remove(n)} data-testid="note-delete">Ištrinti</button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}

      {draft && (() => {
        const p = at(draft);
        return (
          <div style={{ position: 'absolute', left: p.x, top: p.y, pointerEvents: 'auto' }}>
            <span className="-translate-x-1/2 -translate-y-full absolute inline-flex items-center rounded-[2px] border border-dashed border-[hsl(var(--ink-2))] bg-card px-1.5 py-0.5" aria-hidden="true">
              <StickyNote className="h-4 w-4" />
            </span>
            <div className="absolute left-0 top-1 z-10">
              <NoteEditor onSave={save} onCancel={() => setDraft(null)} />
            </div>
          </div>
        );
      })()}
    </div>
  );
}
