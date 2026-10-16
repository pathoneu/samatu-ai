/**
 * OutlineToolPanel — the instruction, the numbers and the choices of the active outline tool
 * (2026-10-16): what the next click does, what the result measures next to the room table's area,
 * what the save will change in the estimate — said BEFORE „Išsaugoti", never after. Enter saves,
 * Z steps back, Esc cancels (TakeoffViewer's Esc chain).
 */
import { useEffect, useMemo, useRef } from 'react';
import { Scissors, Combine, SquareDashed, Undo2, X, Check } from 'lucide-react';
import { formatNumberLT, shoelaceAreaM2 } from '@/lib/measureGeometry';
import { displayRotationFor, normalizeRotation } from '@/lib/viewerEngine/pageRotation';
import { roomPageOf } from '@/lib/roomZones';
import { displaySizePt, pctRingToPts } from '@/lib/outlineTools';
import { openingCounts } from '@/lib/mergeReextract';
import { MERGE_REFUSED } from './OutlineToolLayer';
import { mergeFinishWarning } from '@/lib/outlineToolSave';

// A perimeter the person typed is never replaced by a re-read (api/room_outline.py keeps `user_override`):
// say so, instead of promising that the walls follow the new outline.
const TYPED_PERIMETER = new Set(['user_override', 'manual']);
function wallsSentence(room) {
  if (room && TYPED_PERIMETER.has(String(room.perimetras_saltinis || ''))) {
    const p = Number(room.perimetras_m);
    return `Sienos ${room.nr}: lieka jūsų įrašytas perimetras${p > 0 ? ` (${formatNumberLT(p, 2)} m)` : ''} — kontūras jo nekeičia.`;
  }
  return `Sienos ${room?.nr ?? ''} perskaitomos iš brėžinio pagal naują kontūrą.`;
}

const TITLE = { split: 'Padalyti kontūrą', merge: 'Sujungti su kita patalpa', subtract: 'Atimti iš kontūro' };
const ICON = { split: Scissors, merge: Combine, subtract: SquareDashed };

export default function OutlineToolPanel({
  tool, rooms = [], saving = false, canSave = false, scale = null, pageSizePt = null, pageRotation = 0,
  onChange, onUndo, onCancel, onSave,
}) {
  const size = useMemo(
    () => displaySizePt(pageSizePt, displayRotationFor(normalizeRotation(pageRotation))),
    [pageSizePt, pageRotation],
  );
  const m2 = (ring, holes = []) => (scale?.calibrated && size && ring
    ? Math.max(0, shoelaceAreaM2(pctRingToPts(ring, size), scale) - holes.reduce((s, h) => s + shoelaceAreaM2(pctRingToPts(h, size), scale), 0))
    : null);
  const fmt = (v) => (v == null ? '— (lapo mastelis nenustatytas)' : `${formatNumberLT(v, 2)} m²`);
  const byNr = useMemo(() => new Map((rooms || []).map((r) => [String(r?.nr), r])), [rooms]);
  const table = (nr) => {
    const v = Number(byNr.get(String(nr))?.plotas_m2);
    return v > 0 ? v : null;
  };

  // Enter saves, Z steps back — while no text field has the keyboard.
  const keys = useRef({ onSave, onUndo, canSave, saving });
  useEffect(() => { keys.current = { onSave, onUndo, canSave, saving }; });
  useEffect(() => {
    const onKey = (e) => {
      if (e.target?.closest?.('input, textarea, select, [contenteditable]')) return;
      if (e.key === 'Enter' && keys.current.canSave && !keys.current.saving) { e.preventDefault(); keys.current.onSave?.(); }
      else if ((e.key === 'z' || e.key === 'Z') && !e.metaKey && !e.ctrlKey && !e.altKey) { e.preventDefault(); keys.current.onUndo?.(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  if (!tool) return null;

  const Icon = ICON[tool.mode];
  const room = byNr.get(tool.nr);
  const name = room?.pavadinimas ? ` ${room.pavadinimas}` : '';
  const btn = 'inline-flex items-center gap-1 px-2 py-1 rounded-[2px] border border-border text-[12px] hover:bg-muted disabled:opacity-40 disabled:hover:bg-transparent';
  const primary = 'inline-flex items-center gap-1 px-2.5 py-1 rounded-[2px] bg-primary text-primary-foreground text-[12px] hover:bg-primary/90 disabled:opacity-50';

  let body = null;
  if (tool.mode === 'split') {
    if (!tool.parts) {
      body = (
        <p>{tool.a ? '2) Spustelėkite linijos pabaigą kitoje patalpos pusėje — kontūras bus perkirptas per ją.' : '1) Spustelėkite, kur linija prasideda (prilimpa prie kontūro ir sienų).'}</p>
      );
    } else if (tool.keep == null) {
      body = <p>Spustelėkite dalį, kuri lieka patalpai <b>{tool.nr}</b>. Kitą dalį galėsite priskirti kitai patalpai arba neįtraukti.</p>;
    } else {
      const kept = tool.parts[tool.keep];
      const other = tool.parts[1 - tool.keep];
      const candidates = (rooms || []).filter((r) => String(r?.nr) !== tool.nr
        && (!(Array.isArray(r.polygon_pct) && r.polygon_pct.length >= 3) || roomPageOf(r) === tool.page)
        && r?._konturas?.saltinis !== 'sujungta');
      const pick = tool.otherNr ? byNr.get(String(tool.otherNr)) : null;
      body = (
        <div className="space-y-1.5">
          <p>
            Lieka <b>{tool.nr}</b>: <span className="mono tabular">{fmt(m2(kept.ring, kept.holes))}</span>
            {table(tool.nr) != null && <span className="text-muted-foreground"> · lentelėje {formatNumberLT(table(tool.nr), 2)} m²</span>}
          </p>
          <label className="flex items-center gap-2">
            <span>Kita dalis (<span className="mono tabular">{fmt(m2(other.ring, other.holes))}</span>):</span>
            <select
              value={tool.otherNr || ''}
              onChange={(e) => onChange((cur) => ({ ...cur, otherNr: e.target.value }))}
              className="h-7 px-1.5 rounded-[2px] border border-input bg-background text-[12px] max-w-[260px]"
              data-testid="split-other-room"
              aria-label="Kam priskirti kitą dalį"
            >
              <option value="">Neįtraukti — atmesti šią dalį</option>
              {candidates.map((r) => (
                <option key={r.nr} value={String(r.nr)}>
                  Priskirti patalpai {r.nr}{r.pavadinimas ? ` ${r.pavadinimas}` : ''}{Number(r.plotas_m2) > 0 ? ` (${formatNumberLT(Number(r.plotas_m2), 2)} m²)` : ''}{Array.isArray(r.polygon_pct) && r.polygon_pct.length >= 3 ? ' — jos kontūras bus pakeistas' : ''}
                </option>
              ))}
            </select>
          </label>
          <p className="text-muted-foreground">
            {pick
              ? `Patalpa ${pick.nr} gaus šią dalį kaip savo kontūrą. `
              : 'Ši dalis neliks niekieno kontūre. '}
            Plotai sąmatoje lieka iš lentelės. {wallsSentence(room)}{pick ? ` ${wallsSentence(pick)}` : ''}
          </p>
        </div>
      );
    }
  } else if (tool.mode === 'merge') {
    if (tool.union && tool.targetNr) {
      const sum = (table(tool.nr) || 0) + (table(tool.targetNr) || 0);
      const target = byNr.get(String(tool.targetNr));
      const carried = openingCounts(target?.elementai);
      const finishWarning = mergeFinishWarning(room, target, tool.nr, tool.targetNr);
      body = (
        <div className="space-y-1.5">
          <p>
            <b>{tool.nr}</b> + <b>{tool.targetNr}</b> → <span className="mono tabular">{fmt(m2(tool.union.ring, tool.union.holes))}</span>
            {sum > 0 && <span className="text-muted-foreground"> · lentelėje {formatNumberLT(table(tool.nr) || 0, 2)} + {formatNumberLT(table(tool.targetNr) || 0, 2)} = {formatNumberLT(sum, 2)} m²</span>}
          </p>
          <p className="text-muted-foreground">
            Sąmatoje {tool.nr} skaičiuos <b className="text-foreground">abiejų patalpų plotą</b>
            {sum > 0 ? ` (${formatNumberLT(table(tool.nr) || 0, 2)} + ${formatNumberLT(table(tool.targetNr) || 0, 2)} m² iš eksplikacijos)` : ''}
            {carried.langai || carried.durys ? ` ir ${tool.targetNr} angas (${[carried.langai ? `langai: ${carried.langai}` : null, carried.durys ? `durys: ${carried.durys}` : null].filter(Boolean).join(', ')})` : ''}.
            {' '}Visam plotui taikoma {tool.nr} apdaila{target?.paskirtis && room?.paskirtis && target.paskirtis !== room.paskirtis ? ` (${tool.targetNr} paskirtis „${target.paskirtis}" nebetaikoma)` : ''}.
            {' '}{tool.targetNr} lieka sąraše kaip „sujungta į {tool.nr}" — atskirų eilučių neturės.
            {' '}{TYPED_PERIMETER.has(String(room?.perimetras_saltinis || ''))
              ? `Sienos: jūsų įrašyti perimetrai sudedami (${formatNumberLT(Number(room?.perimetras_m) || 0, 2)} + ${formatNumberLT(Number(target?.perimetras_m) || 0, 2)} m), bendros sienos atkarpa — jei ji buvo siena — atimama iš abiejų pusių.`
              : `Sienos ${tool.nr} perskaitomos iš brėžinio pagal sujungtą kontūrą.`}
          </p>
          {finishWarning && (
            <p className="text-foreground border-l-2 border-primary pl-2" data-testid="merge-finish-warning">{finishWarning}</p>
          )}
        </div>
      );
    } else {
      body = (
        <p>
          Spustelėkite gretimos patalpos kontūrą šiame lape. Sujungiami tik besiliečiantys kontūrai.
          {tool.refused && <span className="block text-destructive mt-1">{tool.refused.nr}: {MERGE_REFUSED[tool.refused.status]}</span>}
        </p>
      );
    }
  } else if (tool.mode === 'subtract') {
    const holes = tool.holes || [];
    const gross = m2(tool.ring);
    const cut = holes.reduce((s, h) => s + (m2(h) || 0), 0);
    body = (
      <div className="space-y-1.5">
        <div className="flex items-center gap-1.5">
          {[['rect', 'Stačiakampis — tempkite'], ['poly', 'Daugiakampis — spustelėkite kampus']].map(([id, label]) => (
            <button key={id} type="button" aria-pressed={tool.shape === id}
              className={tool.shape === id ? `${btn} bg-muted border-primary/50` : btn}
              onClick={() => onChange((cur) => ({ ...cur, shape: id, draft: [] }), { snapshot: false })}
            >{label}</button>
          ))}
        </div>
        <p>
          Plotas: <span className="mono tabular">{fmt(gross)}</span>
          {holes.length > 0 && <> − <span className="mono tabular">{fmt(cut)}</span> = <b className="mono tabular">{fmt(gross == null ? null : gross - cut)}</b></>}
          {table(tool.nr) != null && <span className="text-muted-foreground"> · lentelėje {formatNumberLT(table(tool.nr), 2)} m²</span>}
        </p>
        {holes.length > 0 && (
          <ul className="flex flex-wrap gap-1.5" data-testid="subtract-holes">
            {holes.map((h, i) => (
              <li key={i} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[2px] border border-border bg-muted/50">
                <span className="mono tabular">{i + 1}. {fmt(m2(h))}</span>
                <button type="button" title="Pašalinti išpjovą" aria-label={`Pašalinti ${i + 1} išpjovą`}
                  className="hover:text-destructive"
                  onClick={() => onChange((cur) => ({ ...cur, holes: cur.holes.filter((_, k) => k !== i), dirty: true }))}
                ><X className="w-3 h-3" /></button>
              </li>
            ))}
          </ul>
        )}
        <p className="text-muted-foreground">
          {tool.shape === 'poly'
            ? 'Spustelėkite kampus; uždarykite spustelėję pirmą tašką arba dukart. '
            : 'Tempkite stačiakampį patalpos viduje (kolona, įmontuota spinta, šachta). '}
          Kontūro perimetras nekinta — išpjovų kraštai saugomi atskirai. Sąmatoje grindų ir lubų plotas lieka iš lentelės: išpjova keičia nubrėžtą plotą, rodomą šalia.
        </p>
      </div>
    );
  }

  return (
    <div
      className="absolute top-2 left-1/2 -translate-x-1/2 z-30 w-[min(560px,calc(100%-16px))] rounded-[2px] border border-border bg-card text-[12px] text-foreground shadow-md"
      data-testid="outline-tool-panel"
      data-mode={tool.mode}
    >
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border">
        <Icon className="w-3.5 h-3.5 text-primary" />
        <span className="font-medium">{TITLE[tool.mode]}</span>
        <span className="text-muted-foreground truncate">· {tool.nr}{name}</span>
        <span className="ml-auto inline-flex items-center gap-1">
          <button type="button" className={btn} onClick={onUndo} disabled={!tool.history?.length} title="Žingsnis atgal (Z)">
            <Undo2 className="w-3.5 h-3.5" />Atgal
          </button>
          <button type="button" className={btn} onClick={onCancel} title="Atšaukti (Esc) — niekas neišsaugoma">
            <X className="w-3.5 h-3.5" />Atšaukti
          </button>
          <button type="button" className={primary} onClick={onSave} disabled={!canSave || saving} data-testid="outline-tool-save"
            title="Išsaugoti (Enter) — sienos bus perskaitytos iš naujo, kiekiai perskaičiuoti">
            <Check className="w-3.5 h-3.5" />{saving ? 'Saugoma…' : (tool.mode === 'merge' ? 'Sujungti' : 'Išsaugoti')}
          </button>
        </span>
      </div>
      <div className="px-3 py-2 leading-snug">{body}</div>
    </div>
  );
}
