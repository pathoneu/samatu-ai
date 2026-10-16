/**
 * AiChat — „Pokalbis": questions about THIS project, docked as the workspace's third right-panel tab
 * (togal-v2 W11, Togal capability J: Togal.CHAT with selection pills).
 *
 * What it does, honestly:
 *   - asks `POST /chat-project` with `{project_id, messages, selection}` — the server reads the project from
 *     the database (never a copy sent from here), keeps the last 12 turns, and puts the selected rooms' read
 *     facts and the selected lines' ledgers in front of the question (api/chat_selection.py);
 *   - the PILLS above the box are exactly the selection sent: the room in focus on the drawing, rooms clicked
 *     in the chips, lines added from the Kiekiai panel. Each is removable. Under every answer, the pills of what
 *     the model was really GIVEN (`given` from the server) — and what it was not;
 *   - read-only: the chat changes nothing; a different quantity is typed in „Sąmata" by him;
 *   - 👍 / 👎 under an answer is a row in the learning journal (`pokalbis_taip` / `pokalbis_ne`).
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { Info, Loader2, Plus, Send, ThumbsDown, ThumbsUp, X } from 'lucide-react';
import { API_BASE } from '@/lib/apiBase';
import { logCorrection } from '@/lib/projectStore';
import { chatFeedbackCorrection } from '@/lib/learningEvents';
import {
  EMPTY_SELECTION, addRoom, addRow, answerParts, chatRequest, givenPills, removePill, rowLabel, selectedRoomNrs,
  selectionPayload, selectionPills, toggleRoom,
} from '@/lib/chatSelection';

// Every entry is answerable from what is sent (the project context, or the selection).
const SUGGESTED_QUESTIONS = [
  'Kiek dažomo ploto šiose patalpose?',
  'Iš kur paimtas šių patalpų plotas?',
  'Kuris kambarys didžiausias?',
  'Kiek eilučių dar be kainos?',
];

const HONESTY = 'Atsakymai pagal programos perskaitytus duomenis, ne iš brėžinio tiesiogiai.';

function Pill({ label, focus = false, onRemove = null, muted = false }) {
  return (
    <span
      className={`inline-flex items-center gap-1 max-w-full rounded-sm border px-1.5 py-0.5 text-[11px] leading-4 ${muted
        ? 'border-border text-muted-foreground bg-muted/40'
        : 'border-primary/40 text-foreground bg-primary/10'}`}
      title={focus ? `${label} — pažymėta brėžinyje` : label}
    >
      <span className="truncate">{label}</span>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Pašalinti: ${label}`}
          className="shrink-0 rounded-sm text-muted-foreground hover:text-foreground"
        >
          <X className="w-3 h-3" />
        </button>
      )}
    </span>
  );
}

export default function AiChat({
  project,
  focusedRoomNr = null,
  activeRow = null,          // the line selected in the Kiekiai panel — offered as one click
  addRequest = null,         // {kind: 'row'|'room', row?, nr?, nonce} — „Pridėti į pokalbį" from elsewhere
}) {
  const [messages, setMessages] = useState([]);   // {role: 'user'|'assistant', text, given?, isError?, vote?}
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [selection, setSelection] = useState(EMPTY_SELECTION);
  const [showRooms, setShowRooms] = useState(false);
  const scrollRef = useRef(null);

  const projectId = project?.id || null;
  const rooms = useMemo(
    () => (project?.v8_rooms?.length ? project.v8_rooms : (project?.patalpos || [])),
    [project?.v8_rooms, project?.patalpos]);

  // A new project is a new conversation.
  useEffect(() => { setMessages([]); setSelection(EMPTY_SELECTION); }, [projectId]);
  // Another room in focus brings the focus pill back.
  useEffect(() => {
    setSelection((s) => (s.droppedFocus && s.droppedFocus !== String(focusedRoomNr ?? '') ? { ...s, droppedFocus: null } : s));
  }, [focusedRoomNr]);
  useEffect(() => {
    if (!addRequest) return;
    if (addRequest.kind === 'row' && addRequest.row) setSelection((s) => addRow(s, addRequest.row));
    if (addRequest.kind === 'room' && addRequest.nr != null) setSelection((s) => addRoom(s, addRequest.nr));
  }, [addRequest]);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, loading]);

  const pills = selectionPills(selection, project, focusedRoomNr);
  const selectedNrs = new Set(selectedRoomNrs(selection, focusedRoomNr));
  const activeRowId = activeRow ? (activeRow.id || activeRow._id || null) : null;
  const canAddActiveRow = Boolean(activeRow && activeRowId && !selection.rows.includes(String(activeRowId)));

  const ask = async (question) => {
    const q = String(question || '').trim();
    if (!q || loading || !projectId) return;
    const history = messages;
    const body = chatRequest(projectId, history, q, selectionPayload(selection, focusedRoomNr));
    setMessages((prev) => [...prev, { role: 'user', text: q }]);
    setInput('');
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/chat-project`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const json = await res.json().catch(() => ({}));
      if (res.ok && json.status === 'ok') {
        setMessages((prev) => [...prev, { role: 'assistant', text: json.answer, given: json.given || null, question: q }]);
      } else {
        const why = res.status === 404 ? 'Šio projekto serveryje neradau — perkraukite puslapį.'
          : res.status === 429 ? 'Per daug klausimų iš eilės — palaukite minutę.'
            : (json.error || json.detail || 'Atsakymo gauti nepavyko.');
        setMessages((prev) => [...prev, { role: 'assistant', text: String(why), isError: true }]);
      }
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', text: 'Ryšio klaida — bandykite dar kartą.', isError: true }]);
    } finally {
      setLoading(false);
    }
  };

  const vote = (index, up) => {
    const m = messages[index];
    if (!m || m.isError || m.vote === (up ? 'up' : 'down')) return;
    setMessages((prev) => prev.map((x, i) => (i === index ? { ...x, vote: up ? 'up' : 'down' } : x)));
    const ev = chatFeedbackCorrection({
      question: m.question, answer: m.text, up,
      selection: { rooms: (m.given?.rooms || []).map((r) => r.nr), rows: (m.given?.rows || []).map((r) => r.id) },
    });
    if (ev && projectId) logCorrection(projectId, ev);
  };

  return (
    <div className="h-full flex flex-col bg-card" data-testid="chat-panel">
      {/* What this is — before anything is asked, and always. */}
      <div className="shrink-0 px-3 py-2 border-b border-border bg-muted/30 text-[11px] leading-4 text-muted-foreground flex gap-1.5">
        <Info className="w-3.5 h-3.5 mt-px shrink-0" />
        <span>
          {HONESTY} Pokalbis nieko nekeičia — kiekį pakeisite žingsnyje „Sąmata".
        </span>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3 bg-background">
        {messages.length === 0 && (
          <div className="text-sm text-muted-foreground py-2">
            <p className="mb-1 text-foreground">Klauskite apie šį projektą.</p>
            <p className="mb-3 text-xs">
              Pažymėkite patalpas ir eilutes apačioje — atsakymas bus pirmiausia apie jas, su jų skaičiais.
            </p>
            <div className="space-y-1.5">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => ask(q)}
                  title="Paspauskite — klausimas bus išsiųstas iš karto"
                  className="block w-full text-left text-xs px-3 py-1.5 bg-card border border-border rounded-sm hover:border-foreground/30 hover:bg-muted/50 transition-colors text-foreground"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => {
          if (m.role === 'user') {
            return (
              <div key={i} className="flex justify-end">
                <div className="max-w-[85%] px-3 py-2 rounded-sm text-sm whitespace-pre-wrap bg-foreground text-background">
                  {m.text}
                </div>
              </div>
            );
          }
          const { pills: gotPills, notes } = givenPills(m.given);
          return (
            <div key={i} className="flex flex-col items-start gap-1" data-testid="chat-answer">
              <div
                className={`max-w-[92%] px-3 py-2 rounded-sm text-sm whitespace-pre-wrap ${m.isError
                  ? 'bg-destructive/10 border border-destructive/20 text-destructive'
                  : 'bg-card border border-border text-foreground'}`}
              >
                {answerParts(m.text).map((part, k) => (part.bold
                  ? <strong key={k} className="font-semibold">{part.text}</strong>
                  : <span key={k}>{part.text}</span>))}
              </div>
              {!m.isError && (
                <div className="max-w-[92%] flex flex-wrap items-center gap-1 text-[11px] text-muted-foreground">
                  <span>{gotPills.length ? 'Pokalbis gavo:' : 'Pažymėtų nebuvo — atsakyta pagal visą projektą.'}</span>
                  {gotPills.map((p) => <Pill key={p.key} label={p.label} muted />)}
                  {notes.map((n) => <span key={n} className="w-full">{n}</span>)}
                  <span className="ml-auto inline-flex gap-0.5">
                    <button
                      type="button"
                      onClick={() => vote(i, true)}
                      aria-label="Atsakymas tiko"
                      aria-pressed={m.vote === 'up'}
                      title="Tiko — įrašoma į mokymosi žurnalą"
                      className={`p-1 rounded-sm border ${m.vote === 'up' ? 'border-primary text-primary bg-primary/10' : 'border-transparent hover:border-border'}`}
                    >
                      <ThumbsUp className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => vote(i, false)}
                      aria-label="Atsakymas netiko"
                      aria-pressed={m.vote === 'down'}
                      title="Netiko — įrašoma į mokymosi žurnalą"
                      className={`p-1 rounded-sm border ${m.vote === 'down' ? 'border-destructive text-destructive bg-destructive/10' : 'border-transparent hover:border-border'}`}
                    >
                      <ThumbsDown className="w-3.5 h-3.5" />
                    </button>
                  </span>
                </div>
              )}
            </div>
          );
        })}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-card border border-border px-3 py-2 rounded-sm flex items-center gap-2 text-muted-foreground text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              Ieškau projekto duomenyse…
            </div>
          </div>
        )}
      </div>

      {/* The selection that goes with the next question */}
      <div className="shrink-0 border-t border-border px-3 pt-2 pb-1 space-y-1.5 bg-card" data-testid="chat-pills">
        <div className="flex flex-wrap items-center gap-1">
          <span className="text-[11px] text-muted-foreground mr-0.5">Klausimui:</span>
          {pills.length === 0 && <span className="text-[11px] text-muted-foreground">visas projektas</span>}
          {pills.map((p) => (
            <Pill
              key={p.key}
              label={p.label}
              focus={p.focus}
              onRemove={() => setSelection((s) => removePill(s, p, focusedRoomNr))}
            />
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-1">
          <button
            type="button"
            onClick={() => setShowRooms((v) => !v)}
            aria-expanded={showRooms}
            className="inline-flex items-center gap-0.5 text-[11px] text-primary hover:underline"
          >
            <Plus className="w-3 h-3" /> Patalpos
          </button>
          {canAddActiveRow && (
            <button
              type="button"
              onClick={() => setSelection((s) => addRow(s, activeRow))}
              className="inline-flex items-center gap-0.5 text-[11px] text-primary hover:underline truncate max-w-[70%]"
              title="Pridėti eilutę, pažymėtą skydelyje „Kiekiai“"
            >
              <Plus className="w-3 h-3 shrink-0" /> <span className="truncate">{rowLabel(activeRow)}</span>
            </button>
          )}
        </div>
        {showRooms && (
          <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto" data-testid="chat-room-chips">
            {rooms.map((r) => {
              const nr = String(r?.nr ?? '');
              const on = selectedNrs.has(nr);
              return (
                <button
                  key={nr}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setSelection((s) => toggleRoom(s, nr, focusedRoomNr))}
                  className={`rounded-sm border px-1.5 py-0.5 text-[11px] ${on
                    ? 'border-primary bg-primary/10 text-foreground'
                    : 'border-border text-muted-foreground hover:text-foreground'}`}
                  title={r?.pavadinimas || nr}
                >
                  {nr}{r?.pavadinimas ? ` ${r.pavadinimas}` : ''}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={(e) => { e.preventDefault(); ask(input); }} className="shrink-0 p-3 pt-1.5 bg-card">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Pvz., kiek dažomo ploto šiose patalpose?"
            aria-label="Klausimas apie projektą"
            disabled={loading}
            className="flex-1 px-3 py-2 border border-border bg-background rounded-sm text-sm focus:outline-none focus:border-foreground/40 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            title={input.trim() ? 'Siųsti klausimą' : 'Pirmiausia įrašykite klausimą'}
            aria-label="Siųsti klausimą"
            className="px-3 py-2 bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-30 rounded-sm"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
