import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { FileSpreadsheet, Upload, Trash2, FileUp, Star } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { format } from 'date-fns';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import {
  getPriceLists, createPriceList, deletePriceList,
  setDefaultPriceList, pullPriceListsFromBackend,
} from '@/lib/projectStore';
import { API_BASE as API } from '@/lib/apiBase';
import { parseCsv, describeUnreadablePrices } from '@/lib/priceListCsv';

// The CSV reader lives in lib/priceListCsv.js (tested there, beside the
// .xlsx reader's twin rules in backend/api/price_lists.py).

// Task 5 (2026-09-02): .xlsx goes to the backend (openpyxl), because the
// contractor keeps his kainynas in Excel and a browser-side xlsx reader would
// mean shipping a zip+XML parser to every visitor. CSV keeps the client parser
// above — it needs no round trip and works offline.
async function parseXlsxViaBackend(file) {
  const form = new FormData();
  form.append('file', file, file.name);
  let res;
  try {
    res = await fetch(`${API}/api/price-lists/parse-xlsx`, {
      method: 'POST',
      credentials: 'include',
      body: form,
    });
  } catch {
    throw new Error('Nepavyko pasiekti serverio. Patikrinkite interneto ryšį.');
  }
  let body = null;
  try { body = await res.json(); } catch { /* non-JSON error page */ }
  if (!res.ok) {
    if (res.status === 401) throw new Error('Sesija baigėsi — prisijunkite iš naujo.');
    throw new Error(body?.detail || `Serveris grąžino klaidą (${res.status})`);
  }
  if (!Array.isArray(body?.items)) throw new Error('Serveris grąžino netikėtą atsakymą');
  return body;
}

export default function PriceLists() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isImporting, setIsImporting] = useState(false);

  const { data: priceLists = [], isLoading } = useQuery({
    queryKey: ['priceLists'],
    // Backend is the source of truth since 2026-09-02; the pull refreshes the
    // localStorage cache the rest of the app reads synchronously. A failed pull
    // leaves the cache intact, so the page still shows what this browser has.
    queryFn: async () => {
      await pullPriceListsFromBackend({ force: true });
      return getPriceLists();
    },
  });

  const handleCreate = async () => {
    if (!name.trim()) return;
    setIsSaving(true);
    createPriceList({ name: name.trim(), company_name: company.trim(), items: [], total_items: 0 });
    queryClient.invalidateQueries({ queryKey: ['priceLists'] });
    setDialogOpen(false);
    setName('');
    setCompany('');
    setIsSaving(false);
    toast.success('Kainynas sukurtas');
  };

  const handleDelete = (id) => {
    deletePriceList(id);
    queryClient.invalidateQueries({ queryKey: ['priceLists'] });
    toast.success('Kainynas ištrintas');
  };

  // "Numatytasis" — the kainynas used to fill prices automatically after a new
  // analysis. One at a time; clicking the star again clears it.
  const handleToggleDefault = (pl) => {
    setDefaultPriceList(pl.id);
    queryClient.invalidateQueries({ queryKey: ['priceLists'] });
    toast.success(pl.is_default
      ? `„${pl.name}“ nebe numatytasis kainynas`
      : `„${pl.name}“ — numatytasis kainynas. Kainos bus užpildomos automatiškai po naujos analizės.`);
  };

  const saveImported = (items, file, skipped = 0, problems = []) => {
    const safeName = file.name.replace(/\.(csv|xlsx|xls)$/i, '').slice(0, 60)
      || 'Importuotas kainynas';
    createPriceList({
      name: safeName,
      company_name: '',
      items,
      total_items: items.length,
    });
    queryClient.invalidateQueries({ queryKey: ['priceLists'] });
    toast.success(
      `Importuota ${items.length} eil. iš „${file.name}“`
      + (skipped ? ` (praleista ${skipped} eil. be aprašymo arba be kainos)` : ''),
    );
    // Rows whose price cell held something that is not a price („sutartinė",
    // „15–20 €") are named, so he can fix the cell instead of hunting for them.
    const unreadable = describeUnreadablePrices(problems, t);
    if (unreadable) {
      toast.warning(t('priceLists.unreadableTitle', { count: problems.length }), {
        description: unreadable,
        duration: 20000,
      });
    }
  };

  // Sprint §30 + Task 5: bulk import — CSV parsed here, .xlsx by the backend.
  const handleImport = async (file) => {
    if (!file) return;
    const isExcel = /\.(xlsx|xls)$/i.test(file.name);
    if (isExcel) {
      setIsImporting(true);
      try {
        const parsed = await parseXlsxViaBackend(file);
        saveImported(parsed.items, file, parsed.skipped_rows || 0, parsed.problem_rows || []);
      } catch (e) {
        toast.error(`„Excel“ klaida: ${e.message}`);
      } finally {
        setIsImporting(false);
      }
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const { items, skippedRows, problemRows } = parseCsv(reader.result);
        if (items.length === 0) {
          toast.error('CSV neturi tinkamų eilučių');
          const unreadable = describeUnreadablePrices(problemRows, t);
          if (unreadable) toast.warning(t('priceLists.unreadableTitle', { count: problemRows.length }), { description: unreadable, duration: 20000 });
          return;
        }
        saveImported(items, file, skippedRows, problemRows);
      } catch (e) {
        toast.error(`CSV klaida: ${e.message}`);
      }
    };
    reader.onerror = () => toast.error('Nepavyko nuskaityti failo');
    reader.readAsText(file, 'utf-8');
  };

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Kainynai</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Valdykite įmonės kainų sąrašus. Pažymėkite žvaigždute numatytąjį —
            jo kainos bus įrašomos automatiškai po naujos analizės.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Sprint §30 + Task 5: import — parses skyrius/aprasymas/vnt/kaina
              from CSV (in the browser) or .xlsx (server-side, openpyxl). */}
          <input
            type="file"
            id="csv-import-input"
            accept=".xlsx,.xls,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(e) => {
              const f = e.target.files?.[0];
              // Reset first, so picking the SAME file twice still fires onChange.
              e.target.value = '';
              handleImport(f);
            }}
            className="hidden"
          />
          <Button
            asChild
            variant="outline"
            disabled={isImporting}
            title="Importuoti kainas iš „Excel“ (.xlsx) arba CSV failo. Stulpeliai: skyrius, aprašymas, vnt, kaina"
          >
            <label htmlFor="csv-import-input" className="cursor-pointer">
              <FileUp className="w-4 h-4 mr-2" />
              {isImporting ? 'Įkeliama…' : 'Importuoti Excel / CSV'}
            </label>
          </Button>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button className="bg-primary hover:bg-primary/90 text-primary-foreground">
              <Upload className="w-4 h-4 mr-2" />
              Naujas kainynas
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-card border-border">
            <DialogHeader>
              <DialogTitle className="text-foreground">Naujas kainynas</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-2">
              <div>
                <Label className="text-sm text-muted-foreground">Pavadinimas</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Pvz., 2024 m. kainynas" className="mt-1.5 bg-background border-border" />
              </div>
              <div>
                <Label className="text-sm text-muted-foreground">Įmonė</Label>
                <Input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="UAB Statyba" className="mt-1.5 bg-background border-border" />
              </div>
              <Button
                onClick={handleCreate}
                disabled={isSaving || !name.trim()}
                className="w-full bg-primary hover:bg-primary/90 text-primary-foreground"
              >
                {isSaving ? 'Saugoma...' : 'Sukurti'}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-4 border-muted border-t-primary rounded-full animate-spin" />
        </div>
      ) : priceLists.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20">
          <div className="w-16 h-16 rounded-2xl bg-secondary flex items-center justify-center mb-4">
            <FileSpreadsheet className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="font-semibold text-foreground mb-1">Dar nėra kainynų</h3>
          <p className="text-sm text-muted-foreground text-center max-w-md">
            Įkelkite savo „Excel“ (.xlsx) arba CSV kainyną — stulpeliai:
            skyrius, aprašymas, vnt, kaina.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {priceLists.map(pl => (
            <div key={pl.id} className="bg-card border border-border rounded-xl p-5 flex items-center justify-between group">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <FileSpreadsheet className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground flex items-center gap-2">
                    {pl.name}
                    {pl.is_default && (
                      <span className="text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded-sm bg-primary/10 text-primary">
                        Numatytasis
                      </span>
                    )}
                  </h3>
                  <div className="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
                    {/* Separators are rendered BETWEEN parts, not before them —
                        a list with no company_name used to open with a stray •. */}
                    {[
                      pl.company_name,
                      `${(pl.items || []).length} eil.`,
                      format(new Date(pl.created_date || pl.created_at || Date.now()), 'yyyy-MM-dd'),
                    ].filter(Boolean).map((part, i) => (
                      <React.Fragment key={part}>
                        {i > 0 && <span>•</span>}
                        <span>{part}</span>
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1">
                {/* Numatytasis — the list used for the automatic fill after a
                    new analysis. Always visible when set, so the user can see
                    which prices will land without hovering. */}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleToggleDefault(pl)}
                  title={pl.is_default
                    ? 'Nebenaudoti šio kainyno automatiškai'
                    : 'Naudoti šį kainyną automatiškai naujuose projektuose'}
                  aria-pressed={!!pl.is_default}
                  /* Was hover-only: on a touch screen, and for anyone who does
                     not sweep the pointer down the list, the star and the bin
                     did not exist. (Design §5 — jokių veiksmų tik užvedus
                     pelę.) */
                  className={pl.is_default
                    ? 'text-primary'
                    : 'text-muted-foreground/70 hover:text-primary'}
                >
                  <Star className={`w-4 h-4 ${pl.is_default ? 'fill-current' : ''}`} />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleDelete(pl.id)}
                  title="Ištrinti kainyną"
                  className="text-muted-foreground/70 hover:text-destructive"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
