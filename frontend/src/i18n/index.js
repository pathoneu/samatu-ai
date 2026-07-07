/**
 * i18n — react-i18next initialisation for Pathon public pages.
 *
 * Lithuanian is the DEFAULT and source-of-truth language; English is an
 * additive translation of the public-facing pages only (authenticated app
 * screens are intentionally still hard-coded LT).
 *
 * Language choice persists to localStorage under `pathon_lang`. If nothing is
 * stored we fall back to 'lt' — LT must always render identically to the
 * founder-approved copy. `changeAppLanguage()` switches i18next live and
 * writes the choice; also mirrors <html lang="…"> for a11y / SEO.
 *
 * Import once in main.jsx (side-effect init). Components use useTranslation().
 */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import lt from './lt.json';
import en from './en.json';

export const LANG_STORAGE_KEY = 'pathon_lang';
export const SUPPORTED_LANGS = ['lt', 'en'];

// Persisted choice → else default 'lt'. Never anything but a supported lang.
function initialLang() {
  try {
    const stored = localStorage.getItem(LANG_STORAGE_KEY);
    if (stored && SUPPORTED_LANGS.includes(stored)) return stored;
  } catch {
    /* localStorage unavailable — fall through to default */
  }
  return 'lt';
}

const startLang = initialLang();

i18n.use(initReactI18next).init({
  resources: {
    lt: { translation: lt },
    en: { translation: en },
  },
  lng: startLang,
  fallbackLng: 'lt',
  supportedLngs: SUPPORTED_LANGS,
  interpolation: {
    escapeValue: false, // React already escapes
  },
  returnObjects: true, // allow t('...feats', { returnObjects: true }) arrays
});

// Keep <html lang> in sync (a11y + SEO). Safe on SSR-less client.
function syncHtmlLang(lng) {
  try {
    if (typeof document !== 'undefined') document.documentElement.lang = lng;
  } catch {
    /* no-op */
  }
}
syncHtmlLang(startLang);

/** Switch the active language live and persist the choice. */
export function changeAppLanguage(lng) {
  if (!SUPPORTED_LANGS.includes(lng)) return;
  i18n.changeLanguage(lng);
  try {
    localStorage.setItem(LANG_STORAGE_KEY, lng);
  } catch {
    /* storage unavailable — choice simply won't persist */
  }
  syncHtmlLang(lng);
}

export default i18n;
