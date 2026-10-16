/**
 * LearningJournal — „Įsiminta: N" at the end of the step bar, the „Mokymosi žurnalas" behind it
 * (togal-v2 W11, Togal capability L).
 *
 * N counts this project's `corrections` rows — every accept, reject or edit of an AI result, from every surface
 * (rows, rooms, outlines, symbols, questions, chat thumbs, Nustatymai). The list is the server's sentences
 * (api/learning_journal.py), newest first. Re-read whenever a surface stores a row (LEARNING_EVENT).
 * Recorded, never „the model learned": what is claimed is that his fix was written down, here, for him.
 */

import { useEffect, useState } from 'react';
import { GraduationCap } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { LEARNING_EVENT, correctionsCsvUrl, fetchCorrections } from '@/lib/projectStore';

// The server stores UTC; he reads his own clock.
function when(iso) {
  const d = iso ? new Date(iso) : null;
  if (!d || Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('lt-LT', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export default function LearningJournal({ projectId }) {
  const [rows, setRows] = useState([]);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (typeof window === 'undefined' || !projectId) return undefined;
    const onLogged = (e) => { if (e?.detail?.projectId === projectId) setNonce((n) => n + 1); };
    window.addEventListener(LEARNING_EVENT, onLogged);
    return () => window.removeEventListener(LEARNING_EVENT, onLogged);
  }, [projectId]);

  useEffect(() => {
    let alive = true;
    if (projectId) fetchCorrections(projectId, { limit: 500 }).then((list) => { if (alive) setRows(list); });
    return () => { alive = false; };
  }, [projectId, nonce]);

  if (!projectId) return null;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid="learning-count"
          aria-label={`Įsiminta: ${rows.length} — mokymosi žurnalas`}
          className="ml-auto shrink-0 inline-flex items-center gap-1.5 rounded-sm border border-border px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:border-foreground/30"
          title="Jūsų pataisymai ir patvirtinimai šiame projekte — įrašyti pas jus"
        >
          <GraduationCap className="w-3.5 h-3.5" aria-hidden />
          Įsiminta: <span className="mono tabular text-foreground">{rows.length}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-96 p-0" data-testid="learning-journal">
        <div className="px-3 py-2 border-b border-border">
          <div className="text-sm font-medium text-foreground">Mokymosi žurnalas</div>
          <div className="text-[11px] text-muted-foreground">
            Kiekvienas jūsų priėmimas, atmetimas ar pataisymas šiame projekte, naujausi viršuje.
          </div>
        </div>
        {rows.length === 0 ? (
          <p className="px-3 py-3 text-xs text-muted-foreground">
            Dar nieko. Spauskite „Teisinga“ prie eilutės, atsakykite į patikros klausimą ar pataisykite kontūrą — tai bus įrašyta čia.
          </p>
        ) : (
          <ul className="max-h-80 overflow-y-auto">
            {rows.map((c, i) => (
              <li
                key={`${c.id || c.field_path}-${i}`}
                className="px-3 py-1.5 text-xs border-b border-border/40 last:border-b-0"
              >
                <div className="text-foreground">{c.sentence || c.field_path}</div>
                <div className="mono tabular text-[10.5px] text-muted-foreground">{when(c.occurred_at)}</div>
              </li>
            ))}
          </ul>
        )}
        <div className="px-3 py-2 border-t border-border">
          <a
            href={correctionsCsvUrl(projectId)}
            download
            data-testid="learning-csv"
            className="text-xs underline underline-offset-2 text-primary"
          >
            Atsisiųsti visą žurnalą (CSV)
          </a>
        </div>
      </PopoverContent>
    </Popover>
  );
}
