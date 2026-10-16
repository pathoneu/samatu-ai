/**
 * SudetisBlock — „Sudėtis": what this sąmata line is made of (togal-v2 W9).
 *
 * Renders GET …/rows/{id}/sudetis as is: the labour, each material with its
 * quantity and the sentence that explains it („norma 1,25 kg/m² × 308,32 m² =
 * 385,40 kg"). The server never re-derives a „Medžiagos" row — it shows that
 * row's own quantity, with the norm only where the norm reproduces it — so this
 * block never disagrees with the sąmata.
 */
import { useEffect, useState } from 'react';
import { getSudetis } from '@/lib/assembliesApi';

const RUSIS = { darbas: 'Darbas', medziaga: 'Medžiaga', mechanizmai: 'Mechanizmai' };

function eur(v) {
  return `${(Math.round((Number(v) || 0) * 100) / 100).toLocaleString('lt-LT', {
    minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function qty(v, unit) {
  if (v == null) return '—';
  return `${Number(v).toLocaleString('lt-LT', { maximumFractionDigits: 2 })} ${unit || ''}`.trim();
}

export default function SudetisBlock({ projectId, row }) {
  const [state, setState] = useState({ data: null, error: null, loading: false });
  const rowId = row?.id;
  useEffect(() => {
    if (!projectId || !rowId) return undefined;
    let alive = true;
    setState({ data: null, error: null, loading: true });
    getSudetis(projectId, rowId)
      .then((data) => { if (alive) setState({ data, error: null, loading: false }); })
      .catch((e) => {
        if (!alive) return;
        setState({
          data: null,
          loading: false,
          error: e.status === 404
            ? 'Šios eilutės dar nėra išsaugotame projekte — sudėtis bus rodoma, kai projektas išsisaugos.'
            : (e.detail || 'Nepavyko gauti sudėties'),
        });
      });
    return () => { alive = false; };
  }, [projectId, rowId]);

  if (!projectId || !rowId) return null;
  const { data, error, loading } = state;
  return (
    <section aria-label="Sudėtis" className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-[10px] uppercase tracking-wide text-muted-foreground font-semibold">Sudėtis</p>
        {data?.eilute?.kodas && (
          <span className="font-mono text-[11px] text-muted-foreground" title="Eilutės kodas">{data.eilute.kodas}</span>
        )}
      </div>
      {loading && <p className="text-xs text-muted-foreground">Kraunama…</p>}
      {error && <p className="text-xs text-muted-foreground">{error}</p>}
      {data && (
        <>
          {data.rinkinys && (
            <p className="text-[11px] text-muted-foreground">
              Rinkinys: {data.rinkinys.name}{data.rinkinys.is_default ? ' (numatyta — iš skaičiavimo taisyklių)' : ''}
            </p>
          )}
          {data.medziaga && (
            <p className="text-[11px] text-muted-foreground">
              Tai medžiagos eilutė — jos kiekį paaiškina darbo eilutės sudėtis.
            </p>
          )}
          <ul className="space-y-1.5">
            {data.komponentai.map((c, i) => (
              <li key={`${c.pavadinimas}-${i}`} className="rounded-sm border border-border px-2.5 py-1.5">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-xs text-foreground min-w-0">
                    <span className="text-muted-foreground">{RUSIS[c.rusis] || c.rusis} · </span>
                    {c.pavadinimas}
                  </span>
                  <span className="mono tabular text-xs text-foreground shrink-0">{qty(c.kiekis, c.vnt)}</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-snug mt-0.5">{c.sakinys}</p>
                {c.kaina != null && c.kiekis != null && (
                  <p className="text-[11px] text-muted-foreground tabular mt-0.5">
                    {eur(c.kaina)} / {c.vnt} × {qty(c.kiekis, c.vnt)} = {eur(c.kaina * c.kiekis)}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
