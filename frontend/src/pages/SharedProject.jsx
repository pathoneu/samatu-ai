/**
 * SharedProject — public read-only project viewer (SM04).
 *
 * URL: /share/:token. No login required, no AuthProvider needed for fetch.
 * Renders project name, totals summary, room list, and the kiekiai
 * (darbu_sarasas) grouped by skyrius. Edit affordances are omitted.
 */

import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Loader2, AlertCircle, Eye, ArrowLeft, Building2 } from 'lucide-react';
import { API_BASE as API } from '../lib/apiBase';

function fmtEur(v) {
  return v != null ? `${Number(v).toFixed(2)} €` : '—';
}
function fmtNum(v, digits = 1) {
  return v != null && Number.isFinite(Number(v))
    ? Number(v).toFixed(digits) : '—';
}

export default function SharedProject() {
  const { token } = useParams();
  const [state, setState] = useState({ loading: true, error: null, project: null });

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/share/${token}`)
      .then(async r => {
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body?.detail || `HTTP ${r.status}`);
        return body;
      })
      .then(body => { if (!cancelled) setState({ loading: false, error: null, project: body }); })
      .catch(e => { if (!cancelled) setState({ loading: false, error: e.message, project: null }); });
    return () => { cancelled = true; };
  }, [token]);

  if (state.loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        <Loader2 className="w-5 h-5 mr-2 animate-spin" /> Kraunama...
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="max-w-md text-center">
          <AlertCircle className="w-10 h-10 text-destructive mx-auto mb-3" />
          <h1 className="text-lg font-semibold text-foreground mb-1">Nuoroda netinkama</h1>
          <p className="text-sm text-muted-foreground">{state.error}</p>
          <p className="text-xs text-muted-foreground mt-3">
            Galbūt ji buvo atšaukta savininko arba jūs įvedėte ne tą.
          </p>
        </div>
      </div>
    );
  }

  const p = state.project;
  const data = p?.data || {};
  const patalpos = data.patalpos || data.v8_rooms || [];
  const darbai = (data.darbu_sarasas || []).filter(d => (d.kiekis || 0) > 0);
  const sumNoVat = darbai.reduce((s, d) => s + (d.kiekis || 0) * (d.kaina || 0), 0);
  // Reverse-VAT (atvirkštinis PVM) for renovation: no output VAT — must match the
  // Excel/PDF export, which already does this. Otherwise the share link over-states
  // the price by 21% and prints an illegal VAT line. (2026-06-19 deliverable hunt.)
  const reverseVat = (p.vat_mode || '').toLowerCase() === 'reverse_vat'
    || (p.archetipas || '').toLowerCase() === 'renovacija';
  const vatRate = reverseVat ? 0 : (p.vat_rate || 21) / 100;
  const sumWithVat = sumNoVat * (1 + vatRate);
  const totalArea = patalpos.reduce((s, r) => s + (r.plotas_m2 || 0), 0);

  // Group darbai by skyrius for clean presentation.
  const grouped = {};
  for (const d of darbai) {
    const k = d.skyrius || d.kategorija || 'Kiti darbai';
    (grouped[k] = grouped[k] || []).push(d);
  }
  const skyriai = Object.keys(grouped).sort((a, b) => a.localeCompare(b, 'lt'));

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto px-4 py-6 lg:py-10">
        {/* Read-only banner */}
        <div className="flex items-center gap-2 mb-4 px-3 py-2 bg-primary/10 border border-primary/30 rounded-lg text-xs text-foreground">
          <Eye className="w-3.5 h-3.5 text-primary" />
          <span className="font-medium">Peržiūros režimas</span>
          <span className="text-muted-foreground">— skaitoma kopija. Negalima redaguoti.</span>
        </div>

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-foreground">{p.name || 'Projektas'}</h1>
          {p.company_name && (
            <p className="text-sm text-muted-foreground mt-0.5 flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5" /> {p.company_name}
            </p>
          )}
          <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat label="Patalpos" value={patalpos.length} />
            <Stat label="Plotas" value={`${fmtNum(totalArea)} m²`} />
            <Stat label="Pozicijos" value={darbai.length} />
            <Stat label={reverseVat ? 'Suma (be PVM)' : 'Suma su PVM'} value={fmtEur(sumWithVat)} />
          </div>
        </div>

        {/* Patalpos */}
        {patalpos.length > 0 && (
          <Section title="Patalpos">
            <div className="overflow-x-auto -mx-1">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-muted-foreground border-b border-border">
                    <th className="text-left py-2 pr-3 font-medium">Nr.</th>
                    <th className="text-left py-2 pr-3 font-medium">Pavadinimas</th>
                    <th className="text-left py-2 pr-3 font-medium">Paskirtis</th>
                    <th className="text-right py-2 pr-3 font-medium">Plotas</th>
                    <th className="text-right py-2 font-medium">Lubos</th>
                  </tr>
                </thead>
                <tbody>
                  {patalpos.map(r => (
                    <tr key={r.nr} className="border-b border-border/40 last:border-0">
                      <td className="py-1.5 pr-3 font-mono text-xs">{r.nr}</td>
                      <td className="py-1.5 pr-3">{r.pavadinimas}</td>
                      <td className="py-1.5 pr-3 text-muted-foreground">{r.paskirtis}</td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">{fmtNum(r.plotas_m2)} m²</td>
                      <td className="py-1.5 text-right tabular-nums">
                        {fmtNum(r.lubu_aukstis_m, 2)} m
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        )}

        {/* Pozicijos / kiekiai */}
        {skyriai.length > 0 ? (
          <Section title="Kiekių žiniaraštis">
            <div className="space-y-5">
              {skyriai.map(skyrius => {
                const items = grouped[skyrius];
                const sub = items.reduce((s, d) => s + (d.kiekis || 0) * (d.kaina || 0), 0);
                return (
                  <div key={skyrius}>
                    <div className="flex items-center justify-between mb-1.5 pb-1 border-b border-border">
                      <h3 className="text-sm font-semibold text-foreground">{skyrius}</h3>
                      <span className="text-xs text-muted-foreground tabular-nums">
                        {items.length} pozicijos · {fmtEur(sub)}
                      </span>
                    </div>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-[11px] text-muted-foreground">
                          <th className="text-left py-1 pr-2 font-medium w-8">Nr.</th>
                          <th className="text-left py-1 pr-2 font-medium">Aprašymas</th>
                          <th className="text-right py-1 pr-2 font-medium">Kiekis</th>
                          <th className="text-right py-1 pr-2 font-medium">Vnt.</th>
                          <th className="text-right py-1 pr-2 font-medium">Kaina</th>
                          <th className="text-right py-1 font-medium">Suma</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((d, idx) => (
                          <tr key={d.eil_nr || idx} className="border-t border-border/30">
                            <td className="py-1 pr-2 font-mono text-[11px] text-muted-foreground">
                              {d.eil_nr || idx + 1}
                            </td>
                            <td className="py-1 pr-2">{d.aprasymas}</td>
                            <td className="py-1 pr-2 text-right tabular-nums">{fmtNum(d.kiekis, 2)}</td>
                            <td className="py-1 pr-2 text-right text-muted-foreground">{d.mato_vnt || d.vnt}</td>
                            <td className="py-1 pr-2 text-right tabular-nums">{fmtEur(d.kaina)}</td>
                            <td className="py-1 text-right tabular-nums font-medium">
                              {fmtEur((d.kiekis || 0) * (d.kaina || 0))}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                );
              })}
            </div>
            <div className="mt-6 flex justify-end gap-6 pt-3 border-t border-border text-sm">
              <div>
                <div className="text-muted-foreground text-xs">Suma be PVM</div>
                <div className="font-semibold tabular-nums">{fmtEur(sumNoVat)}</div>
              </div>
              {!reverseVat && (
                <div>
                  <div className="text-muted-foreground text-xs">PVM ({Math.round(vatRate * 100)}%)</div>
                  <div className="font-semibold tabular-nums">{fmtEur(sumNoVat * vatRate)}</div>
                </div>
              )}
              <div>
                <div className="text-muted-foreground text-xs">{reverseVat ? 'VISO (be PVM)' : 'Iš viso'}</div>
                <div className="font-bold tabular-nums">{fmtEur(sumWithVat)}</div>
              </div>
            </div>
            {reverseVat && (
              <p className="mt-2 text-right text-xs text-muted-foreground">
                Atvirkštinis PVM (renovacija): PVM apskaičiuoja ir sumoka pirkėjas (PVMĮ 96 str.).
              </p>
            )}
          </Section>
        ) : (
          <p className="text-sm text-muted-foreground text-center py-8">
            Šio projekto kiekių sąrašas dar tuščias.
          </p>
        )}

        <div className="mt-10 pt-4 border-t border-border text-center">
          <Link to="/" className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
            <ArrowLeft className="w-3 h-3" /> Pathon
          </Link>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="bg-card border border-border rounded-lg px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">
        {label}
      </div>
      <div className="text-sm font-semibold text-foreground tabular-nums truncate">{value}</div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section className="mb-8">
      <h2 className="text-base font-semibold text-foreground mb-3">{title}</h2>
      {children}
    </section>
  );
}
