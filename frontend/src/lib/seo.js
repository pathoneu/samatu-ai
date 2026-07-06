/**
 * Tiny SPA SEO helpers — per-route <title>/<meta> without a helmet dependency.
 *
 * React 18 (no native meta hoisting), so public pages set their own head tags
 * on mount. index.html carries the site-wide defaults (Landing needs no hook);
 * LegalLayout + content pages call setPageMeta() with their own title/intro.
 *
 * NOTE: this only helps crawlers that execute JS (Googlebot does; most AI
 * crawlers do NOT — that's what public/llms.txt + the static index.html head
 * + the planned prerender step are for. See docs/marketing/seo-playbook.md.)
 */

const SITE_NAME = 'Pathon';
const ORIGIN = 'https://pathon.eu';

function upsert(selector, create, apply) {
  let el = document.head.querySelector(selector);
  if (!el) {
    el = create();
    document.head.appendChild(el);
  }
  apply(el);
  return el;
}

function upsertMetaName(name, content) {
  upsert(`meta[name="${name}"]`, () => {
    const m = document.createElement('meta');
    m.setAttribute('name', name);
    return m;
  }, (el) => el.setAttribute('content', content));
}

function upsertMetaProp(property, content) {
  upsert(`meta[property="${property}"]`, () => {
    const m = document.createElement('meta');
    m.setAttribute('property', property);
    return m;
  }, (el) => el.setAttribute('content', content));
}

/**
 * Set page title + description (+ canonical & og mirrors) for the current
 * route. Call from a useEffect on mount. Values are app-controlled strings.
 */
export function setPageMeta({ title, description, path } = {}) {
  const fullTitle = title ? `${title} — ${SITE_NAME}` : undefined;
  if (fullTitle) {
    document.title = fullTitle;
    upsertMetaProp('og:title', fullTitle);
  }
  if (description) {
    upsertMetaName('description', description);
    upsertMetaProp('og:description', description);
  }
  const href = `${ORIGIN}${path ?? window.location.pathname}`;
  upsert('link[rel="canonical"]', () => {
    const l = document.createElement('link');
    l.setAttribute('rel', 'canonical');
    return l;
  }, (el) => el.setAttribute('href', href));
  upsertMetaProp('og:url', href);
}

/**
 * Inject (or replace) a JSON-LD structured-data block by id. `data` must be
 * an app-controlled object (never user input).
 */
export function setJsonLd(id, data) {
  let el = document.getElementById(id);
  if (!el) {
    el = document.createElement('script');
    el.type = 'application/ld+json';
    el.id = id;
    document.head.appendChild(el);
  }
  el.textContent = JSON.stringify(data);
}
