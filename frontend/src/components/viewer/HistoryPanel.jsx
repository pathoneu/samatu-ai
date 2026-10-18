/**
 * HistoryPanel — „Istorija": the last 50 actions on measurements and count marks
 * (lib/measureHistory), newest first, with undo / redo and „Grąžinti iki čia".
 * Undone actions stay listed above, dimmed, until a new action replaces them.
 */
import { Undo2, Redo2, X } from 'lucide-react';
import { HISTORY_LIMIT } from '@/lib/measureHistory';
import { keyText } from '@/lib/viewerShortcuts';

const time = (at) => {
  try { return new Date(at).toLocaleTimeString('lt-LT', { hour: '2-digit', minute: '2-digit' }); } catch { return ''; }
};

export default function HistoryPanel({ history, onUndo, onRedo, onRevertTo, onClose }) {
  const past = [...history.past].reverse();          // newest first
  // Undone actions sit above, in time order too: future[0] was undone first = the latest action, at the
  // top; the next redo (future's last) sits right above the current state.
  const future = history.future;
  const btn = 'p-1 rounded-[2px] text-foreground hover:bg-muted disabled:opacity-40 disabled:hover:bg-transparent';
  return (
    <div className="w-80 max-h-[70vh] flex flex-col rounded-[2px] border border-border bg-card text-card-foreground shadow-lg" data-testid="history-panel">
      <div className="flex items-center gap-1 px-3 py-2 border-b border-border">
        <span className="text-ui font-semibold flex-1">Istorija</span>
        <button type="button" className={btn} disabled={!history.past.length} onClick={onUndo} title={`Atšaukti paskutinį veiksmą (${keyText('undo')})`} aria-label="Atšaukti"><Undo2 className="w-4 h-4" /></button>
        <button type="button" className={btn} disabled={!history.future.length} onClick={onRedo} title={`Grąžinti atšauktą veiksmą (${keyText('redo')})`} aria-label="Grąžinti"><Redo2 className="w-4 h-4" /></button>
        <button type="button" className={btn} onClick={onClose} title="Uždaryti" aria-label="Uždaryti istoriją"><X className="w-4 h-4" /></button>
      </div>
      <div className="flex-1 overflow-y-auto text-meta">
        {!past.length && !future.length && (
          <p className="px-3 py-4 text-muted-foreground leading-relaxed">
            Dar nėra veiksmų. Čia matysite kiekvieną pridėtą, pervadintą ar pašalintą matavimą ir žymę — ir galėsite grįžti į bet kurį žingsnį.
          </p>
        )}
        {future.map((h) => (
          <div key={h.id} className="flex items-start gap-2 px-3 py-1.5 border-b border-border/50 text-muted-foreground" data-history-state="undone">
            <span className="mono tabular text-meta pt-px w-9 shrink-0">{time(h.at)}</span>
            <span className="flex-1 line-through decoration-muted-foreground/50">{h.label}</span>
            <span className="text-meta shrink-0">atšaukta</span>
          </div>
        ))}
        {past.map((h, i) => (
          <div key={h.id} className="group flex items-start gap-2 px-3 py-1.5 border-b border-border/50" data-history-state="done">
            <span className="mono tabular text-meta pt-px w-9 shrink-0 text-muted-foreground">{time(h.at)}</span>
            <span className="flex-1 text-foreground">{h.label}</span>
            {i === 0 ? (
              <span className="text-meta text-muted-foreground shrink-0">dabar</span>
            ) : (
              <button
                type="button"
                onClick={() => onRevertTo(h.id)}
                className="text-meta text-primary hover:underline shrink-0"
                title="Atšaukti visus vėlesnius veiksmus — juos dar bus galima grąžinti"
              >Grąžinti iki čia</button>
            )}
          </div>
        ))}
      </div>
      <p className="px-3 py-1.5 border-t border-border text-meta text-muted-foreground leading-snug">
        Rodoma iki {HISTORY_LIMIT} paskutinių veiksmų. Istorija gyvena tik šiame lange — perkrovus puslapį matavimai lieka, o istorija prasideda iš naujo.
      </p>
    </div>
  );
}
