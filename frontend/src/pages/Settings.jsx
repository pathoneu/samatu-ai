import React, { useState, useEffect } from 'react';
import { useTranslation, Trans } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Save, Building2, KeyRound, User, Download, Upload, AlertCircle, Bug, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  getSettings, saveSettings, getProjects, ensureSettingsPulled, flushSettingsWrites,
  downloadProjectsBackup, importProjectsBackup,
  getArchivedProjects, restoreProject, permanentlyDeleteProject,
} from '@/lib/projectStore';
import { downloadErrorLog, getErrorLog, clearErrorLog } from '@/lib/errorTracker';
import { useConfirm } from '@/components/ui/confirm-provider';
import { useAuth } from '@/lib/authContext';
import { API_BASE } from '@/lib/apiBase';
import BillingSettings from '@/components/billing/BillingSettings';

export default function Settings() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [companyName, setCompanyName] = useState('');
  const [vatRate, setVatRate] = useState('21');
  const [isSaving, setIsSaving] = useState(false);
  // False until this session's settings pull has finished — saving an empty
  // form before then would overwrite the server copy with blanks.
  const [settingsLoaded, setSettingsLoaded] = useState(false);

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
    let alive = true;
    ensureSettingsPulled().then((s) => {
      if (!alive) return;
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
      setSettingsLoaded(true);
    });
    return () => { alive = false; };
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
    if (!/^image\//.test(file.type)) { toast.error(t('settings.toastLogoImageOnly')); return; }
    if (file.size > 500 * 1024) { toast.error(t('settings.toastLogoTooBig')); return; }
    const reader = new FileReader();
    reader.onload = () => setCompanyLogo(reader.result);
    reader.onerror = () => toast.error(t('settings.toastFileReadFail'));
    reader.readAsDataURL(file);
  };

  const handleSave = async () => {
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
    // The browser copy is written already; say whether the server took it too.
    const sent = await flushSettingsWrites();
    setIsSaving(false);
    if (sent === 'ok') toast.success(t('settings.toastSettingsSaved'));
    else toast.error(t('settings.toastSettingsLocalOnly'), { id: 'settings-sync' });
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
      toast.success(t('settings.toastProfileUpdated'));
    } catch (e) {
      toast.error(e.message || t('settings.toastError'));
    } finally {
      setProfileSaving(false);
    }
  };

  const handlePwChange = async () => {
    if (newPw !== newPw2) {
      toast.error(t('settings.toastPwMismatch'));
      return;
    }
    if (newPw.length < 8) {
      toast.error(t('settings.toastPwShort'));
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
      toast.success(t('settings.toastPwChanged'));
      setCurrentPw(''); setNewPw(''); setNewPw2('');
    } catch (e) {
      toast.error(e.message || t('settings.toastError'));
    } finally {
      setPwSaving(false);
    }
  };

  return (
    <div className="p-6 lg:p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-foreground mb-1">{t('settings.title')}</h1>
      <p className="text-sm text-muted-foreground mb-8">{t('settings.subtitle')}</p>

      <div className="space-y-8">
        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <Building2 className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="font-semibold text-foreground">{t('settings.company.heading')}</h2>
              <p className="text-xs text-muted-foreground">{t('settings.company.sub')}</p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <Label className="text-sm text-muted-foreground">{t('settings.company.name')}</Label>
              <Input
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder={t('settings.company.namePlaceholder')}
                className="mt-1.5 bg-background border-border"
              />
            </div>

            <div>
              <Label className="text-sm text-muted-foreground">{t('settings.company.representative')}</Label>
              <Input
                value={vadovas}
                onChange={(e) => setVadovas(e.target.value)}
                placeholder={t('settings.company.representativePlaceholder')}
                className="mt-1.5 bg-background border-border"
              />
              <p className="text-[11px] text-muted-foreground mt-1">{t('settings.company.representativeHint')}</p>
            </div>

            <div>
              <Label className="text-sm text-muted-foreground">{t('settings.company.vatRate')}</Label>
              <Select value={vatRate} onValueChange={setVatRate}>
                <SelectTrigger
                  className="mt-1.5 bg-background border-border"
                  aria-label={t('settings.company.vatRate')}
                  title={t('settings.company.vatRateTitle')}
                >
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
              <Label className="text-sm text-muted-foreground">{t('settings.company.logo')}</Label>
              <div className="mt-1.5 flex items-center gap-3">
                {companyLogo ? (
                  <img src={companyLogo} alt={t('settings.company.logoAlt')} className="h-12 w-auto max-w-[140px] object-contain rounded border border-border bg-white p-1" />
                ) : (
                  <div className="h-12 w-[140px] rounded border border-dashed border-border flex items-center justify-center text-[11px] text-muted-foreground">{t('settings.company.noLogo')}</div>
                )}
                <div className="flex flex-col gap-1">
                  <label className="inline-flex items-center px-3 py-1.5 text-xs rounded border border-border bg-background hover:bg-muted/40 cursor-pointer">
                    {t('settings.company.upload')}
                    <input
                      type="file" accept="image/*" onChange={handleLogoFile} className="hidden"
                      aria-label={t('settings.company.logo')}
                      title={t('settings.company.logoHint')}
                    />
                  </label>
                  {companyLogo && (
                    <button type="button" onClick={() => setCompanyLogo('')} title={t('settings.company.removeLogoTitle')} className="text-[11px] text-muted-foreground hover:text-destructive text-left">
                      {t('settings.company.remove')}
                    </button>
                  )}
                </div>
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">{t('settings.company.logoHint')}</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-sm text-muted-foreground">{t('settings.company.companyCode')}</Label>
                <Input value={imonesKodas} onChange={e => setImonesKodas(e.target.value)} placeholder="123456789" className="mt-1.5 bg-background border-border" />
              </div>
              <div>
                <Label className="text-sm text-muted-foreground">{t('settings.company.pvmCode')}</Label>
                <Input value={pvmKodas} onChange={e => setPvmKodas(e.target.value)} placeholder="LT123456789" className="mt-1.5 bg-background border-border" />
              </div>
              <div className="col-span-2">
                <Label className="text-sm text-muted-foreground">{t('settings.company.address')}</Label>
                <Input value={adresas} onChange={e => setAdresas(e.target.value)} placeholder={t('settings.company.addressPlaceholder')} className="mt-1.5 bg-background border-border" />
              </div>
              <div>
                <Label className="text-sm text-muted-foreground">{t('settings.company.phone')}</Label>
                <Input value={telefonas} onChange={e => setTelefonas(e.target.value)} placeholder="+370 600 00000" className="mt-1.5 bg-background border-border" />
              </div>
              <div>
                <Label className="text-sm text-muted-foreground">{t('settings.company.email')}</Label>
                <Input value={elPastas} onChange={e => setElPastas(e.target.value)} placeholder={t('settings.company.emailPlaceholder')} className="mt-1.5 bg-background border-border" />
              </div>
              <div className="col-span-2">
                <Label className="text-sm text-muted-foreground">{t('settings.company.iban')}</Label>
                <Input value={iban} onChange={e => setIban(e.target.value)} placeholder={t('settings.company.ibanPlaceholder')} className="mt-1.5 bg-background border-border" />
              </div>
            </div>
          </div>
        </div>

        <Button
          onClick={handleSave}
          disabled={isSaving || !settingsLoaded}
          className="bg-primary hover:bg-primary/90 text-primary-foreground font-medium"
        >
          <Save className="w-4 h-4 mr-2" />
          {isSaving ? t('settings.saving') : t('settings.saveAppSettings')}
        </Button>

        {/* Account profile (Phase 13) */}
        {user && (
          <div className="bg-card border border-border rounded-xl p-6">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <User className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h2 className="font-semibold text-foreground">{t('settings.account.heading')}</h2>
                <p className="text-xs text-muted-foreground">{user.email}{user.is_admin && ` · ${t('settings.account.admin')}`}</p>
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <Label htmlFor="profile-name">{t('settings.account.name')}</Label>
                <Input id="profile-name" value={profileName} onChange={e => setProfileName(e.target.value)} className="mt-1.5" />
              </div>
              <div>
                <Label htmlFor="profile-company">{t('settings.account.company')}</Label>
                <Input id="profile-company" value={profileCompany} onChange={e => setProfileCompany(e.target.value)} className="mt-1.5" />
              </div>
              <Button onClick={handleProfileSave} disabled={profileSaving} variant="outline">
                <Save className="w-4 h-4 mr-2" />
                {profileSaving ? t('settings.saving') : t('settings.account.saveProfile')}
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
                <h2 className="font-semibold text-foreground">{t('settings.password.heading')}</h2>
                <p className="text-xs text-muted-foreground">{t('settings.password.sub')}</p>
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <Label htmlFor="cur-pw">{t('settings.password.current')}</Label>
                <Input id="cur-pw" type="password" value={currentPw} onChange={e => setCurrentPw(e.target.value)} className="mt-1.5" />
              </div>
              <div>
                <Label htmlFor="new-pw">{t('settings.password.new')}</Label>
                <Input id="new-pw" type="password" minLength={8} value={newPw} onChange={e => setNewPw(e.target.value)} className="mt-1.5" />
              </div>
              <div>
                <Label htmlFor="new-pw2">{t('settings.password.repeat')}</Label>
                <Input id="new-pw2" type="password" value={newPw2} onChange={e => setNewPw2(e.target.value)} className="mt-1.5" />
              </div>
              <Button
                onClick={handlePwChange}
                disabled={pwSaving || !currentPw || !newPw || !newPw2}
                variant="outline"
              >
                <KeyRound className="w-4 h-4 mr-2" />
                {pwSaving ? t('settings.password.changing') : t('settings.password.change')}
              </Button>
            </div>
          </div>
        )}

        {/* Phase 7: Atsiskaitymas — renders null unless billing is enabled. */}
        <BillingSettings />

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
  const { t } = useTranslation();
  const confirm = useConfirm();
  const [archived, setArchived] = useState(() => getArchivedProjects());

  const refresh = () => setArchived(getArchivedProjects());

  const handleRestore = (id) => {
    restoreProject(id);
    refresh();
    toast.success(t('settings.trash.toastRestored'));
  };

  const handlePermanent = async (id, name) => {
    if (!(await confirm({
      title: t('settings.trash.confirmTitle'),
      description: `${t('settings.trash.confirmDescA')}${name}${t('settings.trash.confirmDescB')}`,
      confirmText: t('settings.trash.confirmDelete'),
      destructive: true,
    }))) return;
    permanentlyDeleteProject(id);
    refresh();
    toast.success(t('settings.trash.toastDeletedForever'));
  };

  const fmtDaysLeft = (archivedAt) => {
    if (!archivedAt) return '—';
    const expires = new Date(archivedAt).getTime() + 30 * 86400 * 1000;
    const days = Math.max(0, Math.round((expires - Date.now()) / 86400 / 1000));
    return t('settings.trash.days', { count: days });
  };

  return (
    <div className="border border-border rounded-xl p-5 space-y-3">
      <div className="flex items-center gap-2">
        <Trash2 className="w-4 h-4 text-foreground" />
        <h3 className="text-sm font-semibold">{t('settings.trash.heading')}</h3>
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
        {t('settings.trash.desc')}
      </p>
      {archived.length === 0 ? (
        <p className="text-xs text-muted-foreground italic">{t('settings.trash.empty')}</p>
      ) : (
        <div className="space-y-2">
          {archived.map(p => (
            <div
              key={p.id}
              className="flex items-center gap-2 px-3 py-2 rounded border border-border/50"
              style={{ background: 'hsl(var(--bg-1))' }}
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-foreground truncate">{p.name || t('settings.trash.untitled')}</div>
                <div className="text-[11px] text-muted-foreground" title={t('settings.trash.leftTitle')}>
                  {t('settings.trash.deletedLabel')} {p._archived_at ? new Date(p._archived_at).toISOString().slice(0, 10) : '—'}
                  {' · '}{t('settings.trash.leftLabel')} {fmtDaysLeft(p._archived_at)}
                </div>
              </div>
              <Button
                onClick={() => handleRestore(p.id)}
                variant="outline"
                size="sm"
                title={t('settings.trash.restoreTitle')}
              >
                {t('settings.trash.restore')}
              </Button>
              {/* The only irreversible action in the product, sitting 8 px from
                  „Atkurti" in an identical outline button. The confirm dialog
                  is honest; the button itself said nothing. (2026-07-28.) */}
              <Button
                onClick={() => handlePermanent(p.id, p.name)}
                variant="outline"
                size="sm"
                title={t('settings.trash.deleteNowTitle')}
                style={{ color: 'hsl(var(--source-ai))' }}
              >
                {t('settings.trash.deleteNow')}
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ErrorLogSection() {
  const { t } = useTranslation();
  const confirm = useConfirm();
  const [count, setCount] = useState(getErrorLog().length);

  const handleExport = () => {
    const entries = getErrorLog();
    if (entries.length === 0) {
      toast.info(t('settings.errorLog.toastEmpty'));
      return;
    }
    downloadErrorLog();
    // Preserve the original LT form-selection logic verbatim: 1 → singular,
    // 2-9 → paucal, ≥10 → genitive plural.
    const n = entries.length;
    const key = n === 1
      ? 'settings.errorLog.toastExportedSingular'
      : n < 10
        ? 'settings.errorLog.toastExportedPaucal'
        : 'settings.errorLog.toastExportedPlural';
    toast.success(t(key, { count: n }));
  };

  const handleClear = async () => {
    if (!(await confirm({
      title: t('settings.errorLog.confirmTitle'),
      confirmText: t('settings.errorLog.confirmClear'),
      destructive: true,
    }))) return;
    clearErrorLog();
    setCount(0);
    toast.success(t('settings.errorLog.toastCleared'));
  };

  return (
    <div className="border border-border rounded-xl p-5 space-y-3">
      <div className="flex items-center gap-2">
        <Bug className="w-4 h-4 text-foreground" />
        <h3 className="text-sm font-semibold">{t('settings.errorLog.heading')}</h3>
      </div>
      <p className="text-xs text-muted-foreground">
        {t('settings.errorLog.desc')}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          onClick={handleExport}
          variant="outline"
          disabled={count === 0}
          title={count === 0 ? t('settings.errorLog.exportBtnEmptyTitle') : t('settings.errorLog.exportBtnTitle', { count })}
        >
          <Download className="w-4 h-4 mr-2" />
          {t('settings.errorLog.exportBtn')} {count > 0 ? `(${count})` : ''}
        </Button>
        <Button
          onClick={handleClear}
          variant="outline"
          disabled={count === 0}
        >
          <Trash2 className="w-4 h-4 mr-2" />
          {t('settings.errorLog.clear')}
        </Button>
      </div>
    </div>
  );
}

function BackupSection() {
  const { t } = useTranslation();
  const [importing, setImporting] = useState(false);
  const projectCount = getProjects().length;

  const handleExport = () => {
    try {
      downloadProjectsBackup();
      toast.success(t('settings.backup.toastExported', { count: projectCount }));
    } catch (e) {
      toast.error(t('settings.backup.toastExportFail', { error: e.message }));
    }
  };

  const handleImport = (file) => {
    if (!file) return;
    setImporting(true);
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        // The import now also sends the restored projects to the server — the
        // counts below are what the server took, not what the file held.
        const result = await importProjectsBackup(reader.result, { mergeStrategy: 'merge' });
        if (result.projects_saved || !result.projects_failed) {
          toast.success(t('settings.backup.toastSaved', { count: result.projects_saved }));
        }
        if (result.projects_kept_server) {
          toast.info(t('settings.backup.toastKeptServer', { count: result.projects_kept_server }),
            { duration: 10000 });
        }
        if (result.projects_failed) {
          // Stays until closed: these projects are not on the server yet.
          toast.error(t('settings.backup.toastSaveFailed', { count: result.projects_failed }),
            { duration: Infinity });
        } else if (!result.projects_kept_server) {
          // Reload only when there is nothing to read — a reload clears the toasts.
          setTimeout(() => window.location.reload(), 800);
        }
      } catch (e) {
        toast.error(e.message || t('settings.backup.toastImportFail'));
      } finally {
        setImporting(false);
      }
    };
    reader.onerror = () => {
      toast.error(t('settings.backup.toastFileReadFail'));
      setImporting(false);
    };
    reader.readAsText(file);
  };

  return (
    <div className="border border-border rounded-xl p-5 space-y-3">
      <div className="flex items-center gap-2">
        <Download className="w-4 h-4 text-foreground" />
        <h3 className="text-sm font-semibold">{t('settings.backup.heading')}</h3>
      </div>
      <p className="text-xs text-muted-foreground">
        {t('settings.backup.descPrefix')}<strong>{projectCount}</strong>{t('settings.backup.descSuffix', { count: projectCount })}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          onClick={handleExport}
          variant="outline"
          disabled={projectCount === 0}
        >
          <Download className="w-4 h-4 mr-2" />
          {t('settings.backup.exportJson')}
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
              {importing ? t('settings.backup.importing') : t('settings.backup.importJson')}
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
          <Trans i18nKey="settings.backup.note"><strong>x</strong></Trans>
        </span>
      </div>
    </div>
  );
}
