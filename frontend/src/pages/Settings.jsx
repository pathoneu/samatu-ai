import React, { useState, useEffect } from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Save, Building2, KeyRound, User, Download, Upload, AlertCircle, Bug, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  getSettings, saveSettings, getProjects,
  downloadProjectsBackup, importProjectsBackup,
  getArchivedProjects, restoreProject, permanentlyDeleteProject,
} from '@/lib/projectStore';
import { downloadErrorLog, getErrorLog, clearErrorLog } from '@/lib/errorTracker';
import { useConfirm } from '@/components/ui/confirm-provider';
import { ltPlural } from '@/lib/ltPlural';
import { useAuth } from '@/lib/authContext';
import { API_BASE } from '@/lib/apiBase';

export default function Settings() {
  const { user } = useAuth();
  const [companyName, setCompanyName] = useState('');
  const [vatRate, setVatRate] = useState('21');
  const [isSaving, setIsSaving] = useState(false);

  // Branding / business-document details (2026-06-19) — rendered into export
  // PDF/Excel headers so the deliverable looks like a real LT pasiūlymas.
  const [companyLogo, setCompanyLogo] = useState('');
  const [imonesKodas, setImonesKodas] = useState('');
  const [pvmKodas, setPvmKodas] = useState('');
  const [adresas, setAdresas] = useState('');
  const [telefonas, setTelefonas] = useState('');
  const [elPastas, setElPastas] = useState('');
  const [iban, setIban] = useState('');
  const [vadovas, setVadovas] = useState('');  // person shown under the company name on exports

  // Profile fields
  const [profileName, setProfileName] = useState('');
  const [profileCompany, setProfileCompany] = useState('');
  const [profileSaving, setProfileSaving] = useState(false);

  // Password change
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [newPw2, setNewPw2] = useState('');
  const [pwSaving, setPwSaving] = useState(false);

  useEffect(() => {
    const s = getSettings();
    if (s.company_name) setCompanyName(s.company_name);
    if (s.vat_rate) setVatRate(String(s.vat_rate));
    if (s.company_logo) setCompanyLogo(s.company_logo);
    if (s.imones_kodas) setImonesKodas(s.imones_kodas);
    if (s.pvm_kodas) setPvmKodas(s.pvm_kodas);
    if (s.adresas) setAdresas(s.adresas);
    if (s.telefonas) setTelefonas(s.telefonas);
    if (s.el_pastas) setElPastas(s.el_pastas);
    if (s.iban) setIban(s.iban);
    if (s.vadovas) setVadovas(s.vadovas);
  }, []);

  useEffect(() => {
    if (user) {
      setProfileName(user.name || '');
      setProfileCompany(user.company_name || '');
    }
  }, [user]);

  const handleLogoFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!/^image\//.test(file.type)) { toast.error('Tinka tik paveikslėlis (PNG/JPG)'); return; }
    if (file.size > 500 * 1024) { toast.error('Logotipas per didelis (max 500 KB)'); return; }
    const reader = new FileReader();
    reader.onload = () => setCompanyLogo(reader.result);
    reader.onerror = () => toast.error('Nepavyko nuskaityti failo');
    reader.readAsDataURL(file);
  };

  const handleSave = () => {
    setIsSaving(true);
    // saveSettings REPLACES the whole object — merge with existing so we never
    // wipe unrelated keys (e.g. price-list prefs stored under the same key).
    saveSettings({
      ...getSettings(),
      company_name: companyName,
      vat_rate: parseInt(vatRate),
      company_logo: companyLogo,
      imones_kodas: imonesKodas,
      pvm_kodas: pvmKodas,
      adresas,
      telefonas,
      el_pastas: elPastas,
      iban,
      vadovas,
    });
    setIsSaving(false);
    toast.success('Nustatymai išsaugoti');
  };

  const handleProfileSave = async () => {
    setProfileSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/profile`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: profileName, company_name: profileCompany }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      toast.success('Profilis atnaujintas');
    } catch (e) {
      toast.error(e.message || 'Klaida');
    } finally {
      setProfileSaving(false);
    }
  };

  const handlePwChange = async () => {
    if (newPw !== newPw2) {
      toast.error('Nauji slaptažodžiai nesutampa');
      return;
    }
    if (newPw.length < 8) {
      toast.error('Naujas slaptažodis turi būti ne trumpesnis nei 8 simboliai');
      return;
    }
    setPwSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/change-password`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      toast.success('Slaptažodis pakeistas');
      setCurrentPw(''); setNewPw(''); setNewPw2('');
    } catch (e) {
      toast.error(e.message || 'Klaida');
    } finally {
      setPwSaving(false);
    }
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
              <Label className="text-sm text-muted-foreground">Atstovas (pareigos, vardas, pavardė)</Label>
              <Input
                value={vadovas}
                onChange={(e) => setVadovas(e.target.value)}
                placeholder="Direktorius Vardas Pavardė"
                className="mt-1.5 bg-background border-border"
              />
              <p className="text-[11px] text-muted-foreground mt-1">Rodoma po įmonės pavadinimu pasiūlyme.</p>
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

            <div>
              <Label className="text-sm text-muted-foreground">Logotipas</Label>
              <div className="mt-1.5 flex items-center gap-3">
                {companyLogo ? (
                  <img src={companyLogo} alt="Logotipas" className="h-12 w-auto max-w-[140px] object-contain rounded border border-border bg-white p-1" />
                ) : (
                  <div className="h-12 w-[140px] rounded border border-dashed border-border flex items-center justify-center text-[11px] text-muted-foreground">Nėra logotipo</div>
                )}
                <div className="flex flex-col gap-1">
                  <label className="inline-flex items-center px-3 py-1.5 text-xs rounded border border-border bg-background hover:bg-muted/40 cursor-pointer">
                    Įkelti…
                    <input type="file" accept="image/*" onChange={handleLogoFile} className="hidden" />
                  </label>
                  {companyLogo && (
                    <button type="button" onClick={() => setCompanyLogo('')} className="text-[11px] text-muted-foreground hover:text-destructive text-left">
                      Pašalinti
                    </button>
                  )}
                </div>
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">PNG/JPG, iki 500 KB. Rodomas eksportuojamų PDF/Excel antraštėje.</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-sm text-muted-foreground">Įmonės kodas</Label>
                <Input value={imonesKodas} onChange={e => setImonesKodas(e.target.value)} placeholder="123456789" className="mt-1.5 bg-background border-border" />
              </div>
              <div>
                <Label className="text-sm text-muted-foreground">PVM mokėtojo kodas</Label>
                <Input value={pvmKodas} onChange={e => setPvmKodas(e.target.value)} placeholder="LT123456789" className="mt-1.5 bg-background border-border" />
              </div>
              <div className="col-span-2">
                <Label className="text-sm text-muted-foreground">Adresas</Label>
                <Input value={adresas} onChange={e => setAdresas(e.target.value)} placeholder="Vilniaus g. 1, Kaunas" className="mt-1.5 bg-background border-border" />
              </div>
              <div>
                <Label className="text-sm text-muted-foreground">Telefonas</Label>
                <Input value={telefonas} onChange={e => setTelefonas(e.target.value)} placeholder="+370 600 00000" className="mt-1.5 bg-background border-border" />
              </div>
              <div>
                <Label className="text-sm text-muted-foreground">El. paštas</Label>
                <Input value={elPastas} onChange={e => setElPastas(e.target.value)} placeholder="info@imone.lt" className="mt-1.5 bg-background border-border" />
              </div>
              <div className="col-span-2">
                <Label className="text-sm text-muted-foreground">IBAN (atsiskaitymams)</Label>
                <Input value={iban} onChange={e => setIban(e.target.value)} placeholder="LT12 3456 7890 1234 5678" className="mt-1.5 bg-background border-border" />
              </div>
            </div>
          </div>
        </div>

        <Button
          onClick={handleSave}
          disabled={isSaving}
          className="bg-primary hover:bg-primary/90 text-primary-foreground font-medium"
        >
          <Save className="w-4 h-4 mr-2" />
          {isSaving ? 'Saugoma...' : 'Išsaugoti programos nustatymus'}
        </Button>

        {/* Account profile (Phase 13) */}
        {user && (
          <div className="bg-card border border-border rounded-xl p-6">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <User className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h2 className="font-semibold text-foreground">Paskyra</h2>
                <p className="text-xs text-muted-foreground">{user.email}{user.is_admin && ' · administratorius'}</p>
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <Label htmlFor="profile-name">Vardas</Label>
                <Input id="profile-name" value={profileName} onChange={e => setProfileName(e.target.value)} className="mt-1.5" />
              </div>
              <div>
                <Label htmlFor="profile-company">Įmonė</Label>
                <Input id="profile-company" value={profileCompany} onChange={e => setProfileCompany(e.target.value)} className="mt-1.5" />
              </div>
              <Button onClick={handleProfileSave} disabled={profileSaving} variant="outline">
                <Save className="w-4 h-4 mr-2" />
                {profileSaving ? 'Saugoma...' : 'Išsaugoti profilį'}
              </Button>
            </div>
          </div>
        )}

        {/* Password change */}
        {user && (
          <div className="bg-card border border-border rounded-xl p-6">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <KeyRound className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h2 className="font-semibold text-foreground">Slaptažodis</h2>
                <p className="text-xs text-muted-foreground">Pakeiskite reguliariai saugumui</p>
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <Label htmlFor="cur-pw">Dabartinis slaptažodis</Label>
                <Input id="cur-pw" type="password" value={currentPw} onChange={e => setCurrentPw(e.target.value)} className="mt-1.5" />
              </div>
              <div>
                <Label htmlFor="new-pw">Naujas slaptažodis (min 8 simb.)</Label>
                <Input id="new-pw" type="password" minLength={8} value={newPw} onChange={e => setNewPw(e.target.value)} className="mt-1.5" />
              </div>
              <div>
                <Label htmlFor="new-pw2">Pakartoti naują slaptažodį</Label>
                <Input id="new-pw2" type="password" value={newPw2} onChange={e => setNewPw2(e.target.value)} className="mt-1.5" />
              </div>
              <Button
                onClick={handlePwChange}
                disabled={pwSaving || !currentPw || !newPw || !newPw2}
                variant="outline"
              >
                <KeyRound className="w-4 h-4 mr-2" />
                {pwSaving ? 'Keičiama...' : 'Pakeisti slaptažodį'}
              </Button>
            </div>
          </div>
        )}

        {/* Sprint §13: Projektų atsarginė kopija (export/import) */}
        <BackupSection />

        {/* Sprint §28: Šiukšliadėžė (soft-deleted projects) */}
        <TrashSection />

        {/* Sprint §24: Klaidų žurnalas eksportui */}
        <ErrorLogSection />
      </div>
    </div>
  );
}

function TrashSection() {
  const confirm = useConfirm();
  const [archived, setArchived] = useState(() => getArchivedProjects());

  const refresh = () => setArchived(getArchivedProjects());

  const handleRestore = (id) => {
    restoreProject(id);
    refresh();
    toast.success('Projektas atstatytas');
  };

  const handlePermanent = async (id, name) => {
    if (!(await confirm({
      title: 'Ištrinti projektą visam laikui?',
      description: `„${name}" bus ištrintas negrįžtamai. Šio veiksmo atšaukti negalėsi.`,
      confirmText: 'Ištrinti',
      destructive: true,
    }))) return;
    permanentlyDeleteProject(id);
    refresh();
    toast.success('Projektas ištrintas visam laikui');
  };

  const fmtDaysLeft = (archivedAt) => {
    if (!archivedAt) return '—';
    const expires = new Date(archivedAt).getTime() + 30 * 86400 * 1000;
    const days = Math.max(0, Math.round((expires - Date.now()) / 86400 / 1000));
    return `${days} d.`;
  };

  return (
    <div className="border border-border rounded-xl p-5 space-y-3">
      <div className="flex items-center gap-2">
        <Trash2 className="w-4 h-4 text-foreground" />
        <h3 className="text-sm font-semibold">Šiukšliadėžė</h3>
        {archived.length > 0 && (
          <span
            className="mono tabular text-[10px] uppercase tracking-wide font-medium px-1.5 py-0 rounded"
            style={{
              background: 'hsl(var(--source-ai) / 0.15)',
              color: 'hsl(var(--source-ai))',
            }}
          >
            {archived.length}
          </span>
        )}
      </div>
      <p className="text-xs text-muted-foreground">
        Ištrinti projektai laikomi 30 dienų — gali atstatyti, jei netyčia ištrynei.
        Po šio termino jie ištrinami visam laikui.
      </p>
      {archived.length === 0 ? (
        <p className="text-xs text-muted-foreground italic">Šiukšliadėžė tuščia.</p>
      ) : (
        <div className="space-y-2">
          {archived.map(p => (
            <div
              key={p.id}
              className="flex items-center gap-2 px-3 py-2 rounded border border-border/50"
              style={{ background: 'hsl(var(--bg-1))' }}
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-foreground truncate">{p.name || 'Be pavadinimo'}</div>
                <div className="text-[11px] text-muted-foreground">
                  Ištrinta: {p._archived_at ? new Date(p._archived_at).toISOString().slice(0, 10) : '—'}
                  {' · '}Liko: {fmtDaysLeft(p._archived_at)}
                </div>
              </div>
              <Button
                onClick={() => handleRestore(p.id)}
                variant="outline"
                size="sm"
              >
                Atstatyti
              </Button>
              <Button
                onClick={() => handlePermanent(p.id, p.name)}
                variant="outline"
                size="sm"
                style={{ color: 'hsl(var(--source-ai))' }}
              >
                Ištrinti dabar
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ErrorLogSection() {
  const confirm = useConfirm();
  const [count, setCount] = useState(getErrorLog().length);

  const handleExport = () => {
    const entries = getErrorLog();
    if (entries.length === 0) {
      toast.info('Klaidų žurnalas tuščias.');
      return;
    }
    downloadErrorLog();
    toast.success(`Eksportuota ${entries.length} klaida${entries.length === 1 ? '' : entries.length < 10 ? 's' : 'ų'}`);
  };

  const handleClear = async () => {
    if (!(await confirm({
      title: 'Išvalyti klaidų žurnalą?',
      confirmText: 'Išvalyti',
      destructive: true,
    }))) return;
    clearErrorLog();
    setCount(0);
    toast.success('Žurnalas išvalytas');
  };

  return (
    <div className="border border-border rounded-xl p-5 space-y-3">
      <div className="flex items-center gap-2">
        <Bug className="w-4 h-4 text-foreground" />
        <h3 className="text-sm font-semibold">Klaidų žurnalas</h3>
      </div>
      <p className="text-xs text-muted-foreground">
        Naršyklės atminty saugoma iki 100 paskutinių klaidų. Eksportuok JSON,
        jei reikia atsiųsti pagalbai. Žurnalas neapima asmeninių duomenų — tik
        klaidos tekstas, puslapis ir laikas.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          onClick={handleExport}
          variant="outline"
          disabled={count === 0}
          title={count === 0 ? 'Žurnalas tuščias' : `Eksportuoti ${count} įrašus`}
        >
          <Download className="w-4 h-4 mr-2" />
          Eksportuoti klaidų žurnalą {count > 0 ? `(${count})` : ''}
        </Button>
        <Button
          onClick={handleClear}
          variant="outline"
          disabled={count === 0}
        >
          <Trash2 className="w-4 h-4 mr-2" />
          Išvalyti
        </Button>
      </div>
    </div>
  );
}

function BackupSection() {
  const [importing, setImporting] = useState(false);
  const projectCount = getProjects().length;

  const handleExport = () => {
    try {
      downloadProjectsBackup();
      toast.success(`Atsarginė kopija atsisiųsta (${projectCount} ${ltPlural(projectCount, 'projektas', 'projektai', 'projektų')})`);
    } catch (e) {
      toast.error(`Nepavyko eksportuoti: ${e.message}`);
    }
  };

  const handleImport = (file) => {
    if (!file) return;
    setImporting(true);
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const result = importProjectsBackup(reader.result, { mergeStrategy: 'merge' });
        toast.success(
          `Importuota: ${result.projects_imported} ${ltPlural(result.projects_imported, 'projektas', 'projektai', 'projektų')}. Iš viso saugykloje: ${result.projects_total}.`
        );
        setTimeout(() => window.location.reload(), 800);
      } catch (e) {
        toast.error(e.message || 'Importas nepavyko');
      } finally {
        setImporting(false);
      }
    };
    reader.onerror = () => {
      toast.error('Nepavyko nuskaityti failo');
      setImporting(false);
    };
    reader.readAsText(file);
  };

  return (
    <div className="border border-border rounded-xl p-5 space-y-3">
      <div className="flex items-center gap-2">
        <Download className="w-4 h-4 text-foreground" />
        <h3 className="text-sm font-semibold">Atsarginė kopija</h3>
      </div>
      <p className="text-xs text-muted-foreground">
        Saugykloje šiuo metu: <strong>{projectCount}</strong> projekt{projectCount === 1 ? 'as' : projectCount % 10 >= 2 && projectCount % 10 <= 9 && (projectCount % 100 < 10 || projectCount % 100 >= 20) ? 'ai' : 'ų'}.
        Eksportuok JSON failą, kad galėtum perkelti projektus į kitą kompiuterį arba atstatyti, jei išvalyta naršyklės istorija.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          onClick={handleExport}
          variant="outline"
          disabled={projectCount === 0}
        >
          <Download className="w-4 h-4 mr-2" />
          Eksportuoti JSON
        </Button>
        <label className="inline-flex items-center">
          <input
            type="file"
            accept="application/json,.json"
            onChange={(e) => handleImport(e.target.files?.[0])}
            disabled={importing}
            className="hidden"
            id="backup-import-file"
          />
          <Button
            asChild
            variant="outline"
            disabled={importing}
          >
            <label htmlFor="backup-import-file" className="cursor-pointer">
              <Upload className="w-4 h-4 mr-2" />
              {importing ? 'Importuojama...' : 'Importuoti JSON'}
            </label>
          </Button>
        </label>
      </div>
      <div
        className="flex items-start gap-2 p-2.5 rounded text-xs"
        style={{
          background: 'hsl(var(--source-ai) / 0.06)',
          color: 'hsl(var(--source-ai))',
          border: '1px solid hsl(var(--source-ai) / 0.2)',
        }}
      >
        <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
        <span>
          Importas <strong>sujungia</strong> projektus pagal ID (naujesni laikai
          perrašo senesnius). PDF brėžiniai NĖRA atsarginėje kopijoje — jie
          saugomi atskirai (IndexedDB) ir nepersikelia tarp kompiuterių.
        </span>
      </div>
    </div>
  );
}
