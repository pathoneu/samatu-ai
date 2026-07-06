/**
 * Consent-gated GA4 loader (Google Consent Mode v2, privacy-first).
 *
 * Rules:
 *  - gtag.js is NOT loaded at all until the visitor grants the "analytics"
 *    category in the CookieBanner (pathon_cookie_consent in localStorage).
 *    This is the strict-GDPR variant of Consent Mode (no cookieless pings).
 *  - Consent defaults are DENIED for all four v2 signals; "analytics" consent
 *    grants analytics_storage, "marketing" grants ad_storage/ad_user_data/
 *    ad_personalization (needed later for Google Ads conversion import).
 *  - The GA4 property id comes from VITE_GA4_ID. Unset (dev/default) → the
 *    whole module is a no-op, so nothing changes until the founder creates
 *    the GA4 property and sets the env var on the host.
 *
 * Wire-up: main.jsx calls initAnalytics() once; CookieBanner dispatches
 * `pathon:cookie-consent-changed` whenever the visitor saves a choice.
 */
import { getCookieConsent } from '@/components/CookieBanner';

const GA_ID = import.meta.env.VITE_GA4_ID;
const CONSENT_EVENT = 'pathon:cookie-consent-changed';

let loaded = false;

function gtag(...args) {
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push(args);
}

function consentSignals(categories) {
  const analytics = !!categories?.analytics;
  const marketing = !!categories?.marketing;
  return {
    analytics_storage: analytics ? 'granted' : 'denied',
    ad_storage: marketing ? 'granted' : 'denied',
    ad_user_data: marketing ? 'granted' : 'denied',
    ad_personalization: marketing ? 'granted' : 'denied',
  };
}

function loadGtag(categories) {
  if (loaded || !GA_ID) return;
  loaded = true;
  gtag('consent', 'default', {
    analytics_storage: 'denied',
    ad_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied',
  });
  gtag('consent', 'update', consentSignals(categories));
  gtag('js', new Date());
  // SPA: page_view is sent manually on route changes via trackPageView().
  gtag('config', GA_ID, { anonymize_ip: true, send_page_view: false });
  const s = document.createElement('script');
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${GA_ID}`;
  document.head.appendChild(s);
  trackPageView();
}

/** Call once at app start; safe to call with no GA_ID (no-op). */
export function initAnalytics() {
  if (!GA_ID) return;
  const consent = getCookieConsent();
  if (consent?.categories?.analytics) loadGtag(consent.categories);
  window.addEventListener(CONSENT_EVENT, (e) => {
    const categories = e?.detail || getCookieConsent()?.categories;
    if (!categories) return;
    if (categories.analytics && !loaded) {
      loadGtag(categories);
    } else if (loaded) {
      gtag('consent', 'update', consentSignals(categories));
    }
  });
}

/** SPA page view (call on route change). No-op until loaded+consented. */
export function trackPageView(path) {
  if (!loaded) return;
  gtag('event', 'page_view', {
    page_location: window.location.href,
    page_path: path ?? window.location.pathname,
    page_title: document.title,
  });
}

/** Business event (e.g. 'sign_up', 'begin_extraction'). Consent-gated. */
export function trackEvent(name, params = {}) {
  if (!loaded) return;
  gtag('event', name, params);
}
