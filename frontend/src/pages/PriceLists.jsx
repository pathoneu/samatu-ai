import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { FileSpreadsheet, Upload, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { format } from 'date-fns';
import { toast } from 'sonner';
import { getPriceLists, createPriceList, deletePriceList } from '@/lib/projectStore';

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

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Kainynai</h1>
          <p className="text-sm text-muted-foreground mt-1">Valdykite įmonės kainų sąrašus</p>
        </div>
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
