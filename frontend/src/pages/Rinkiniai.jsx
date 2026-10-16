/**
 * Rinkiniai — what each work is made of, and what it costs (togal-v2 W9).
 *
 * His own rinkiniai: a work row (by its name and unit) → labour, machinery and
 * materials by norm per unit of work, waste %, and a unit price for each. The
 * „numatyti" ones are built by the server from the calculation rules' own
 * norms — read-only here; „Kopijuoti ir keisti" makes them his.
 *
 * Nothing on this page moves a quantity in a sąmata: a rinkinys explains a row
 * („Sudėtis") and prices it („Pritaikyti rinkinius" in the sąmata).
 */
import React, { useEffect, useState } from 'react';
import { Layers, Plus, Trash2, Copy, Pencil, Check, X } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  copyOfDefault, createAssembly, deleteAssembly, listAssemblies, updateAssembly,
} from '@/lib/assembliesApi';
import { unitPriceSplit } from '@/lib/assemblyPricing';
import { parseLtNumber } from '@/lib/parseLtNumber';

const RUSYS = [
  { value: 'darbas', label: 'Darbas' },
  { value: 'medziaga', label: 'Medžiaga' },
  { value: 'mechanizmai', label: 'Mechanizmai' },
];
const RUSIS_LABEL = Object.fromEntries(RUSYS.map((r) => [r.value, r.label]));

const UNIT_LT = { m2: 'm²', m3: 'm³', vnt: 'vnt.' };
const unitLt = (u) => UNIT_LT[String(u || '').replace(/\.$/, '')] || u || '';

function num(v, digits = 4) {
  if (v == null || v === '') return '—';
  return Number(v).toLocaleString('lt-LT', { maximumFractionDigits: digits });
}
function eur(v) {
  return `${Number(v || 0).toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}
/** Shown as „{vieta}" in the engine's templates; he reads „…". */
const showLabel = (s) => String(s || '').replaceAll('{vieta}', '…');

function toDraft(a) {
  return {
    name: a?.name || '',
    skyrius: a?.skyrius || '',
    taikoma_aprasymas: a?.taikoma?.aprasymas || '',
    taikoma_vnt: a?.taikoma?.vnt || a?.vnt || '',
    kodas: a?.kodas || '',
    komponentai: (a?.komponentai || []).map((c) => ({
      rusis: c.rusis || 'medziaga',
      pavadinimas: c.pavadinimas || '',
      norma: c.norma == null ? '' : String(c.norma).replace('.', ','),
      vnt: c.vnt || '',
      atliekos_proc: c.atliekos_proc ? String(c.atliekos_proc).replace('.', ',') : '',
      kaina: c.kaina == null ? '' : String(c.kaina).replace('.', ','),
      apvalinimas: c.apvalinimas ?? null,
      minimumas: c.minimumas ?? null,
    })),
  };
}

/** Draft → API body; throws an Error with a Lithuanian message on bad input. */
function fromDraft(d) {
  const numOrNull = (s, what) => {
    if (String(s).trim() === '') return null;
    const n = parseLtNumber(s);
    if (!Number.isFinite(n) || n < 0) throw new Error(`Netinkamas skaičius: ${what}`);
    return n;
  };
  if (!d.name.trim()) throw new Error('Įrašykite rinkinio pavadinimą');
  if (!d.taikoma_aprasymas.trim()) throw new Error('Įrašykite, kuriai sąmatos eilutei rinkinys taikomas');
  return {
    name: d.name.trim(),
    skyrius: d.skyrius.trim() || null,
    taikoma: { aprasymas: d.taikoma_aprasymas.trim(), vnt: d.taikoma_vnt.trim() || null, eilutes_id: [] },
    vnt: d.taikoma_vnt.trim() || null,
    kodas: d.kodas.trim() || null,
    komponentai: d.komponentai.map((c, i) => {
      const norma = numOrNull(c.norma, `norma (${i + 1} eil.)`);
      if (norma == null) throw new Error(`Įrašykite normą (${i + 1} eil.)`);
      const atl = numOrNull(c.atliekos_proc, `atliekos (${i + 1} eil.)`) ?? 0;
      if (atl > 100) throw new Error(`Atliekos negali viršyti 100 % (${i + 1} eil.)`);
      if (!c.pavadinimas.trim()) throw new Error(`Įrašykite pavadinimą (${i + 1} eil.)`);
      return {
        rusis: c.rusis, pavadinimas: c.pavadinimas.trim(), norma, vnt: c.vnt.trim() || null,
        atliekos_proc: atl, kaina: numOrNull(c.kaina, `kaina (${i + 1} eil.)`),
        apvalinimas: c.apvalinimas, minimumas: c.minimumas,
      };
    }),
  };
}

function PriceLine({ a }) {
  const s = unitPriceSplit(a);
  if (!s.viso) return <p className="text-xs text-muted-foreground">Kainos dar neįrašytos</p>;
  return (
    <p className="text-xs text-muted-foreground tabular-nums">
      Už 1 {unitLt(a?.taikoma?.vnt || a?.vnt) || 'vnt.'}: darbo kaina {eur(s.darbo)} + medžiagų kaina {eur(s.medziagu)}
      {' '}= <span className="text-foreground font-medium">{eur(s.viso)}</span>
    </p>
  );
}

function ComponentsTable({ a }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-[11px] uppercase text-muted-foreground border-b border-border">
          <tr>
            <th className="text-left font-medium py-1 pr-2">Rūšis</th>
            <th className="text-left font-medium py-1 pr-2">Pavadinimas</th>
            <th className="text-right font-medium py-1 pr-2">Norma</th>
            <th className="text-right font-medium py-1 pr-2">Atliekos</th>
            <th className="text-right font-medium py-1">Kaina</th>
          </tr>
        </thead>
        <tbody>
          {(a.komponentai || []).map((c, i) => (
            <tr key={i} className="border-b border-border/60 last:border-0">
              <td className="py-1 pr-2 text-muted-foreground">{RUSIS_LABEL[c.rusis] || c.rusis}</td>
              <td className="py-1 pr-2">{showLabel(c.pavadinimas)}</td>
              <td className="py-1 pr-2 text-right tabular-nums whitespace-nowrap">
                {num(c.norma)} {unitLt(c.vnt)}/{unitLt(a?.taikoma?.vnt || a?.vnt)}
              </td>
              <td className="py-1 pr-2 text-right tabular-nums">{c.atliekos_proc ? `${num(c.atliekos_proc, 2)} %` : '—'}</td>
              <td className="py-1 text-right tabular-nums">{c.kaina != null ? eur(c.kaina) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Editor({ initial, onCancel, onSaved, assemblyId }) {
  const [d, setD] = useState(() => toDraft(initial));
  const [saving, setSaving] = useState(false);
  const setC = (i, patch) => setD((p) => ({
    ...p, komponentai: p.komponentai.map((c, j) => (j === i ? { ...c, ...patch } : c)),
  }));
  const save = async () => {
    let body;
    try { body = fromDraft(d); } catch (e) { toast.error(e.message); return; }
    setSaving(true);
    try {
      const out = assemblyId ? await updateAssembly(assemblyId, body) : await createAssembly(body);
      toast.success(assemblyId ? 'Rinkinys išsaugotas' : 'Rinkinys sukurtas');
      onSaved(out);
    } catch (e) {
      toast.error(e.detail || 'Nepavyko išsaugoti rinkinio');
    } finally {
      setSaving(false);
    }
  };
  const field = 'mt-1 h-9 bg-background border-border';
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label className="text-xs text-muted-foreground">Pavadinimas
          <Input className={field} value={d.name} onChange={(e) => setD({ ...d, name: e.target.value })} />
        </label>
        <label className="text-xs text-muted-foreground">Kodas
          <Input className={`${field} font-mono`} value={d.kodas} placeholder="pvz. 01.01"
                 onChange={(e) => setD({ ...d, kodas: e.target.value })} />
        </label>
        <label className="text-xs text-muted-foreground sm:col-span-2">Taikoma sąmatos eilutei (pavadinimas)
          <Input className={field} value={d.taikoma_aprasymas}
                 placeholder="pvz. Sienų glaistymas/dažymas"
                 onChange={(e) => setD({ ...d, taikoma_aprasymas: e.target.value })} />
          {d.taikoma_aprasymas.includes('{vieta}') && (
            <span className="block mt-1 text-[11px]">
              „{'{vieta}'}“ — bet kuri pavadinimo dalis (pvz. „Vonios sienų“ ar „ virš 3 m“); ta pati dalis
              įrašoma į medžiagų pavadinimus.
            </span>
          )}
        </label>
        <label className="text-xs text-muted-foreground">Eilutės vienetas
          <Input className={field} value={d.taikoma_vnt} placeholder="m2"
                 onChange={(e) => setD({ ...d, taikoma_vnt: e.target.value })} />
        </label>
        <label className="text-xs text-muted-foreground">Skyrius
          <Input className={field} value={d.skyrius} onChange={(e) => setD({ ...d, skyrius: e.target.value })} />
        </label>
      </div>
      <p className="text-xs text-muted-foreground">
        Norma — kiek sudedamosios dalies reikia vienam eilutės vienetui. Kaina — už vieną sudedamosios
        dalies vienetą. Medžiagos kaina tenka tos eilutės „Medžiagos“ eilutei, jei ji sąmatoje yra; kitaip
        pridedama prie darbo eilutės kainos.
      </p>
      <div className="space-y-2">
        {d.komponentai.map((c, i) => (
          <div key={i} className="grid grid-cols-12 gap-2 items-end">
            <label className="col-span-6 sm:col-span-2 text-[11px] text-muted-foreground">Rūšis
              <select value={c.rusis} onChange={(e) => setC(i, { rusis: e.target.value })}
                      className="mt-1 h-9 w-full rounded-sm border border-border bg-background px-2 text-sm text-foreground">
                {RUSYS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </label>
            <label className="col-span-6 sm:col-span-4 text-[11px] text-muted-foreground">Pavadinimas
              <Input className={field} value={c.pavadinimas} onChange={(e) => setC(i, { pavadinimas: e.target.value })} />
            </label>
            <label className="col-span-3 sm:col-span-1 text-[11px] text-muted-foreground">Norma
              <Input className={`${field} text-right tabular-nums`} inputMode="decimal" value={c.norma}
                     onChange={(e) => setC(i, { norma: e.target.value })} />
            </label>
            <label className="col-span-3 sm:col-span-1 text-[11px] text-muted-foreground">Vnt.
              <Input className={field} value={c.vnt} onChange={(e) => setC(i, { vnt: e.target.value })} />
            </label>
            <label className="col-span-3 sm:col-span-1 text-[11px] text-muted-foreground">Atliekos %
              <Input className={`${field} text-right tabular-nums`} inputMode="decimal" value={c.atliekos_proc}
                     onChange={(e) => setC(i, { atliekos_proc: e.target.value })} />
            </label>
            <label className="col-span-3 sm:col-span-2 text-[11px] text-muted-foreground">Kaina €
              <Input className={`${field} text-right tabular-nums`} inputMode="decimal" value={c.kaina}
                     onChange={(e) => setC(i, { kaina: e.target.value })} />
            </label>
            <Button variant="ghost" size="icon" className="col-span-12 sm:col-span-1 text-muted-foreground hover:text-destructive"
                    title="Pašalinti sudedamąją dalį" aria-label="Pašalinti sudedamąją dalį"
                    onClick={() => setD((p) => ({ ...p, komponentai: p.komponentai.filter((_, j) => j !== i) }))}>
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        ))}
        <Button variant="outline" size="sm"
                onClick={() => setD((p) => ({ ...p, komponentai: [...p.komponentai,
                  { rusis: 'medziaga', pavadinimas: '', norma: '', vnt: '', atliekos_proc: '', kaina: '',
                    apvalinimas: null, minimumas: null }] }))}>
          <Plus className="w-4 h-4 mr-1.5" /> Pridėti sudedamąją dalį
        </Button>
      </div>
      <div className="flex gap-2">
        <Button onClick={save} disabled={saving} className="bg-primary hover:bg-primary/90 text-primary-foreground">
          <Check className="w-4 h-4 mr-1.5" /> {saving ? 'Saugoma…' : 'Išsaugoti'}
        </Button>
        <Button variant="outline" onClick={onCancel}><X className="w-4 h-4 mr-1.5" /> Atšaukti</Button>
      </div>
    </div>
  );
}

function Card({ children }) {
  return <div className="bg-card border border-border rounded-sm p-5 space-y-3">{children}</div>;
}

export default function Rinkiniai() {
  const [list, setList] = useState({ assemblies: [], loaded: false, error: null });
  const [editing, setEditing] = useState(null);   // null | 'new' | { id } | { copyOf }
  const [showDefaults, setShowDefaults] = useState(false);

  const reload = (force = true) => listAssemblies({ force })
    .then((d) => setList({ assemblies: d.assemblies, loaded: true, error: null }))
    .catch((e) => setList((s) => ({ ...s, loaded: true, error: e.detail || 'Nepavyko nuskaityti rinkinių' })));
  useEffect(() => { reload(false); }, []);

  const own = list.assemblies.filter((a) => !a.is_default);
  const defaults = list.assemblies.filter((a) => a.is_default);
  const done = () => { setEditing(null); reload(); };

  const remove = async (a) => {
    if (!window.confirm(`Ištrinti rinkinį „${a.name}“?`)) return;
    try { await deleteAssembly(a.id); toast.success('Rinkinys ištrintas'); reload(); }
    catch (e) { toast.error(e.detail || 'Nepavyko ištrinti rinkinio'); }
  };

  return (
    <div className="p-4 sm:p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Rinkiniai</h1>
          <p className="text-sm text-muted-foreground max-w-2xl mt-1">
            Iš ko susideda kiekvienas darbas: medžiagos pagal normą, atliekos, darbas — ir kiek tai kainuoja,
            atskirai darbo ir medžiagų kaina. Rinkinys sąmatos kiekių nekeičia: jis paaiškina eilutę („Sudėtis“)
            ir ją įkainoja („Pritaikyti rinkinius“ sąmatoje).
          </p>
        </div>
        <Button onClick={() => setEditing('new')} className="bg-primary hover:bg-primary/90 text-primary-foreground">
          <Plus className="w-4 h-4 mr-2" /> Naujas rinkinys
        </Button>
      </div>

      {list.error && <p className="text-sm text-destructive">{list.error}</p>}

      {editing === 'new' && (
        <Card>
          <h2 className="font-semibold text-foreground">Naujas rinkinys</h2>
          <Editor initial={{ komponentai: [{ rusis: 'darbas', pavadinimas: 'Darbas', norma: 1, vnt: '' }] }}
                  onCancel={() => setEditing(null)} onSaved={done} />
        </Card>
      )}
      {editing?.copyOf && (
        <Card>
          <h2 className="font-semibold text-foreground">Kopija: {editing.copyOf.name}</h2>
          <Editor initial={copyOfDefault(editing.copyOf)} onCancel={() => setEditing(null)} onSaved={done} />
        </Card>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">Mano rinkiniai</h2>
        {!list.loaded ? (
          <p className="text-sm text-muted-foreground">Kraunama…</p>
        ) : own.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Dar nėra. Sukurkite naują arba nukopijuokite numatytą rinkinį žemiau ir įrašykite savo kainas.
          </p>
        ) : own.map((a) => (
          <Card key={a.id}>
            {editing?.id === a.id ? (
              <Editor initial={a} assemblyId={a.id} onCancel={() => setEditing(null)} onSaved={done} />
            ) : (
              <>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="font-semibold text-foreground flex items-center gap-2">
                      {a.kodas && <span className="font-mono text-xs text-muted-foreground">{a.kodas}</span>}
                      {a.name}
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      Taikoma: „{showLabel(a.taikoma?.aprasymas)}“{a.taikoma?.vnt ? `, ${unitLt(a.taikoma.vnt)}` : ''}
                    </p>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <Button variant="ghost" size="icon" title="Keisti" aria-label="Keisti"
                            onClick={() => setEditing({ id: a.id })}><Pencil className="w-4 h-4" /></Button>
                    <Button variant="ghost" size="icon" title="Ištrinti" aria-label="Ištrinti"
                            className="text-muted-foreground hover:text-destructive"
                            onClick={() => remove(a)}><Trash2 className="w-4 h-4" /></Button>
                  </div>
                </div>
                <ComponentsTable a={a} />
                <PriceLine a={a} />
              </>
            )}
          </Card>
        ))}
      </section>

      <section className="space-y-3">
        <button type="button" onClick={() => setShowDefaults((v) => !v)}
                className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Layers className="w-4 h-4 text-muted-foreground" />
          Numatyti rinkiniai ({defaults.length}) — iš skaičiavimo taisyklių
          <span className="text-xs font-normal text-muted-foreground">{showDefaults ? 'slėpti' : 'rodyti'}</span>
        </button>
        {showDefaults && (
          <>
            <p className="text-xs text-muted-foreground max-w-2xl">
              Šios normos ir atliekos — tos pačios, pagal kurias programa skaičiuoja „Medžiagos“ eilutes. Jų
              keisti negalima; nukopijavę įrašysite savo kainas ar normas. Jūsų pakeista norma sąmatos „Medžiagos“
              kiekio nekeičia — ji rodoma eilutės sudėtyje ir naudojama kainai.
            </p>
            {defaults.map((a) => (
              <Card key={a.id}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="font-semibold text-foreground flex items-center gap-2">
                      <span className="font-mono text-xs text-muted-foreground">{a.kodas}</span>
                      {a.name}
                      <span className="text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded-sm bg-muted text-muted-foreground">
                        numatyta
                      </span>
                    </h3>
                    <p className="text-xs text-muted-foreground">Taikoma: „{showLabel(a.taikoma?.aprasymas)}“</p>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => setEditing({ copyOf: a })}>
                    <Copy className="w-4 h-4 mr-1.5" /> Kopijuoti ir keisti
                  </Button>
                </div>
                <ComponentsTable a={a} />
              </Card>
            ))}
          </>
        )}
      </section>
    </div>
  );
}
