import React, { useState, useEffect } from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Save, Building2 } from 'lucide-react';
import { toast } from 'sonner';
import { getSettings, saveSettings } from '@/lib/projectStore';

export default function Settings() {
  const [companyName, setCompanyName] = useState('');
  const [vatRate, setVatRate] = useState('21');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    const s = getSettings();
    if (s.company_name) setCompanyName(s.company_name);
    if (s.vat_rate) setVatRate(String(s.vat_rate));
  }, []);

  const handleSave = () => {
    setIsSaving(true);
    saveSettings({ company_name: companyName, vat_rate: parseInt(vatRate) });
    setIsSaving(false);
    toast.success('Nustatymai išsaugoti');
  };

  return (
    <div className="p-6 lg:p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-foreground mb-1">Nustatymai</h1>
      <p className="text-sm text-muted-foreground mb-8">Bendri programos nustatymai</p>

      <div className="space-y-8">
        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <Building2 className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="font-semibold text-foreground">Įmonės informacija</h2>
              <p className="text-xs text-muted-foreground">Numatytieji duomenys naujiems projektams</p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <Label className="text-sm text-muted-foreground">Įmonės pavadinimas</Label>
              <Input
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="UAB Statyba"
                className="mt-1.5 bg-background border-border"
              />
            </div>

            <div>
              <Label className="text-sm text-muted-foreground">PVM tarifas</Label>
              <Select value={vatRate} onValueChange={setVatRate}>
                <SelectTrigger className="mt-1.5 bg-background border-border">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="21">21%</SelectItem>
                  <SelectItem value="9">9%</SelectItem>
                  <SelectItem value="0">0%</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        <Button
          onClick={handleSave}
          disabled={isSaving}
          className="bg-primary hover:bg-primary/90 text-primary-foreground font-medium"
        >
          <Save className="w-4 h-4 mr-2" />
          {isSaving ? 'Saugoma...' : 'Išsaugoti nustatymus'}
        </Button>
      </div>
    </div>
  );
}
