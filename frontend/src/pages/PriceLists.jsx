import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { FileSpreadsheet, Upload, Trash2, FileUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { format } from 'date-fns';
import { toast } from 'sonner';
import { getPriceLists, createPriceList, deletePriceList } from '@/lib/projectStore';

// Sprint §30 (2026-04-29): CSV parser. Supports both `,` and `;` separators
// (LT Excel uses `;` by default). Quoted fields with embedded commas. UTF-8 BOM
// stripped. First row treated as headers.
function parseCsv(text) {
  // Detect separator from first non-empty line
  const cleaned = text.replace(/^﻿/, '');
  const firstLine = cleaned.split(/\r?\n/).find(l => l.trim()) || '';
  const sep = firstLine.includes(';') && !firstLine.includes(',') ? ';'
            : firstLine.split(',').length >= firstLine.split(';').length ? ','
            : ';';

  const rows = [];
  let cur = [];
  let field = '';
  let inQuotes = false;
  for (let i = 0; i < cleaned.length; i++) {
    const ch = cleaned[i];
    if (inQuotes) {
      if (ch === '"' && cleaned[i + 1] === '"') { field += '"'; i++; }
      else if (ch === '"') { inQuotes = false; }
      else { field += ch; }
    } else {
      if (ch === '"') inQuotes = true;
      else if (ch === sep) { cur.push(field); field = ''; }
      else if (ch === '\n' || ch === '\r') {
        if (field || cur.length) { cur.push(field); rows.push(cur); cur = []; field = ''; }
        if (ch === '\r' && cleaned[i + 1] === '\n') i++;
      }
      else { field += ch; }
    }
  }
  if (field || cur.length) { cur.push(field); rows.push(cur); }
  if (rows.length < 2) throw new Error('CSV neturi duomenų eilučių');

  const headers = rows[0].map(h => h.trim().toLowerCase());
  const headerMap = {
    'skyrius': 'skyrius', 'kategorija': 'skyrius',
    'aprasymas': 'aprasymas', 'aprašymas': 'aprasymas', 'pavadinimas': 'aprasymas',
    'vnt': 'mato_vnt', 'mato_vnt': 'mato_vnt', 'matas': 'mato_vnt', 'unit': 'mato_vnt',
    'kaina': 'kaina', 'kaina_eur': 'kaina', 'price': 'kaina',
  };
  const colIdx = {};
  headers.forEach((h, i) => {
    const m = headerMap[h];
    if (m) colIdx[m] = i;
  });
  if (colIdx.aprasymas == null || colIdx.kaina == null) {
    throw new Error('Reikalingi stulpeliai: skyrius, aprasymas, vnt, kaina (kalbantis su Excel ar atsisiųstu CSV)');
  }

  const items = [];
  for (let r = 1; r < rows.length; r++) {
    const row = rows[r];
    if (!row || row.every(c => !c.trim())) continue;
    const aprasymas = (row[colIdx.aprasymas] || '').trim();
    if (!aprasymas) continue;
    const kainaRaw = (row[colIdx.kaina] || '').trim().replace(',', '.').replace(/[^\d.\-]/g, '');
    const kaina = parseFloat(kainaRaw);
    if (!isFinite(kaina)) continue;
    items.push({
      skyrius: colIdx.skyrius != null ? (row[colIdx.skyrius] || '').trim() : 'Kiti darbai',
      aprasymas,
      mato_vnt: colIdx.mato_vnt != null ? (row[colIdx.mato_vnt] || '').trim() : '',
      kaina,
    });
  }
  return items;
}

export default function PriceLists() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const { data: priceLists = [], isLoading } = useQuery({
    queryKey: ['priceLists'],
    queryFn: getPriceLists,
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
    toast.success('Kainynė sukurta');
  };

  const handleDelete = (id) => {
    deletePriceList(id);
    queryClient.invalidateQueries({ queryKey: ['priceLists'] });
    toast.success('Kainynė ištrinta');
  };

  // Sprint §30: bulk CSV import — parse + create new pricelist
  const handleCsvImport = (file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const items = parseCsv(reader.result);
        if (items.length === 0) {
          toast.error('CSV neturi tinkamų eilučių');
          return;
        }
        const safeName = file.name.replace(/\.csv$/i, '').slice(0, 60) || 'Importuota kainynė';
        createPriceList({
          name: safeName,
          company_name: '',
          items,
          total_items: items.length,
        });
        queryClient.invalidateQueries({ queryKey: ['priceLists'] });
        toast.success(`Importuota ${items.length} eilutės iš „${file.name}"`);
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
          <p className="text-sm text-muted-foreground mt-1">Valdykite įmonės kainų sąrašus</p>
        </div>
        <div className="flex items-center gap-2">
          {/* Sprint §30: CSV import — parses skyrius/aprasymas/vnt/kaina columns */}
          <input
            type="file"
            id="csv-import-input"
            accept=".csv,text/csv"
            onChange={(e) => handleCsvImport(e.target.files?.[0])}
            className="hidden"
          />
          <Button asChild variant="outline" title="Importuoti kainas iš CSV failo (skyrius, aprasymas, vnt, kaina)">
            <label htmlFor="csv-import-input" className="cursor-pointer">
              <FileUp className="w-4 h-4 mr-2" />
              Importuoti CSV
            </label>
          </Button>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button className="bg-primary hover:bg-primary/90 text-primary-foreground">
              <Upload className="w-4 h-4 mr-2" />
              Nauja kainynė
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-card border-border">
            <DialogHeader>
              <DialogTitle className="text-foreground">Nauja kainynė</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-2">
              <div>
                <Label className="text-sm text-muted-foreground">Pavadinimas</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Pvz. 2024 m. kainynė" className="mt-1.5 bg-background border-border" />
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
          <h3 className="font-semibold text-foreground mb-1">Dar nėra kainynių</h3>
          <p className="text-sm text-muted-foreground text-center max-w-md">
            Sukurkite kainynę norėdami sekti kainų sąrašus.
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
                  <h3 className="font-semibold text-foreground">{pl.name}</h3>
                  <div className="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
                    {pl.company_name && <span>{pl.company_name}</span>}
                    <span>•</span>
                    <span>{format(new Date(pl.created_date), 'yyyy-MM-dd')}</span>
                  </div>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => handleDelete(pl.id)}
                className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
