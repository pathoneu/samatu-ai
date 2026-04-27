import React, { useState, useEffect } from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Save, Building2, KeyRound, User } from 'lucide-react';
import { toast } from 'sonner';
import { getSettings, saveSettings } from '@/lib/projectStore';
import { useAuth } from '@/lib/authContext';

export default function Settings() {
  const { user } = useAuth();
  const [companyName, setCompanyName] = useState('');
  const [vatRate, setVatRate] = useState('21');
  const [isSaving, setIsSaving] = useState(false);

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
  }, []);

  useEffect(() => {
    if (user) {
      setProfileName(user.name || '');
      setProfileCompany(user.company_name || '');
    }
  }, [user]);

  const handleSave = () => {
    setIsSaving(true);
    saveSettings({ company_name: companyName, vat_rate: parseInt(vatRate) });
    setIsSaving(false);
    toast.success('Nustatymai išsaugoti');
  };

  const handleProfileSave = async () => {
    setProfileSaving(true);
    try {
      const res = await fetch('/api/auth/profile', {
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
      const res = await fetch('/api/auth/change-password', {
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
      </div>
    </div>
  );
}
