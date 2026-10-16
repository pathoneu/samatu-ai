/**
 * RinkiniaiControls — the sąmata table's pieces for rinkiniai and kodai
 * (togal-v2 W9), kept out of ProjectMainView so that shared file only wires
 * them in.
 *
 *   useAssemblies()        — his + the „numatyta" rinkiniai and the section codes
 *   KodasChip              — a row's cost code, click to type his own
 *   priceSplitTitle(item)  — „darbo 4,20 € + medžiagų 1,80 €" for a split price
 *   ApplyAssembliesButton  — „Pritaikyti rinkinius": prices rows from his rinkiniai
 */
import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Layers } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { listAssemblies } from '@/lib/assembliesApi';
import { applyAssembliesToPositions, hasPrices } from '@/lib/assemblyPricing';
import { describeMaterialPrices, describeAmbiguous } from '@/lib/applyPriceList';

function fmtEur(val) {
  return `${Number(val || 0).toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

export function useAssemblies() {
  const [state, setState] = useState({ assemblies: [], kodai: {}, loaded: false });
  useEffect(() => {
    let alive = true;
    listAssemblies()
      .then((d) => { if (alive) setState({ ...d, loaded: true }); })
      .catch(() => { if (alive) setState((s) => ({ ...s, loaded: true })); });
    return () => { alive = false; };
  }, []);
  return state;
}

export function priceSplitTitle(item) {
  if (item?.kaina_darbo == null && item?.kaina_medziagu == null) return null;
  return `Darbo ${fmtEur(item.kaina_darbo || 0)} + medžiagų ${fmtEur(item.kaina_medziagu || 0)}`;
}

/**
 * The row's cost code. Muted when it is the default (from the rinkinys or the
 * section), solid when he typed it. Click → type; Enter saves, an empty field
 * goes back to the default, Escape cancels.
 */
export function KodasChip({ item, kodas, onChange }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const typed = typeof item?.kodas === 'string' && item.kodas.trim() !== '';
  const commit = () => {
    const v = draft.trim().slice(0, 32);
    setEditing(false);
    if (v === (typed ? item.kodas.trim() : '')) return;
    const next = { ...item };
    if (v) next.kodas = v; else delete next.kodas;
    onChange(next);
  };
  if (editing) {
    return (
      <input
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); commit(); }
          if (e.key === 'Escape') setEditing(false);
        }}
        aria-label="Eilutės kodas"
        placeholder={kodas || 'kodas'}
        className="w-16 shrink-0 px-1 py-0.5 border border-primary bg-background rounded-sm text-xs font-mono"
      />
    );
  }
  return (
    <button
      type="button"
      onClick={() => { setDraft(typed ? item.kodas : ''); setEditing(true); }}
      title={typed
        ? 'Jūsų įrašytas kodas — spustelėkite, kad pakeistumėte'
        : 'Kodas iš rinkinio arba skyriaus — spustelėkite, kad įrašytumėte savo'}
      className={`shrink-0 rounded-sm border px-1 py-0.5 text-[11px] font-mono leading-none tabular-nums transition-colors ${
        typed ? 'border-border text-foreground' : 'border-transparent text-muted-foreground hover:border-border'}`}
    >
      {kodas || '—'}
    </button>
  );
}

/** „Pritaikyti rinkinius": prices the rows his rinkiniai cover (labour on the
 *  work row, materials on their „Medžiagos" rows). Hand-typed prices stay. */
export function ApplyAssembliesButton({ project, onProjectChange, assemblies }) {
  const { t } = useTranslation();
  const priced = (assemblies || []).filter((a) => !a.is_default && hasPrices(a));
  const handle = () => {
    const src = project?.darbu_sarasas;
    if (!Array.isArray(src) || !src.length) return;
    const out = applyAssembliesToPositions(src, priced);
    if (!out.applied && !out.materialsPriced) {
      toast.error('Nė vienai eilutei rinkinys netiko — patikrinkite rinkinio „Taikoma eilutei“ pavadinimą ir vienetą.');
      return;
    }
    onProjectChange?.({ ...project, darbu_sarasas: out.items });
    toast.success(`Pritaikyta iš rinkinių: ${out.applied} darbo kainų`,
      { description: describeMaterialPrices(out, t) });
    if (out.ambiguous.length) {
      toast.warning(`${out.ambiguous.length} eil. praleista — joms tinka keli rinkiniai skirtingomis kainomis.`,
        { duration: 8000, description: describeAmbiguous(out.ambiguous, t) });
    }
  };
  return (
    <Button
      variant="outline"
      onClick={handle}
      disabled={!priced.length}
      title={priced.length
        ? 'Įkainoti eilutes pagal jūsų rinkinius: darbo kaina — eilutei, medžiagų — jos „Medžiagos“ eilutėms. Rankomis įvestos kainos lieka.'
        : 'Dar neturite rinkinio su kainomis — susikurkite jį puslapyje „Rinkiniai“'}
      style={{ minHeight: 44, fontSize: 15 }}
    >
      <Layers className="w-4 h-4 mr-2" />
      Pritaikyti rinkinius
    </Button>
  );
}
