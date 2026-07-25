# Sąmatų AI — diegimo planas (beta paleidimas)

**Tikslas:** `samatu.pathon.eu` viešai pasiekiamas per kelias dienas, EU regione (Frankfurt arba Amsterdamas), <€20/mėn., su minimaliu DevOps krūviu vienam savininkui.

**Stack:** FastAPI + uvicorn (Python 3.11+), Vite/React SPA, SQLite arba Postgres, Anthropic API kvietimai (PDF Vision), failų įkėlimai iki 200 MB.

**Auditorija:** ~10 beta vartotojų pirmąją savaitę, Lietuva, GDPR.

---

## 1. Hostingo platformos sprendimas

Lyginu tris kandidatus tiksliam mūsų poreikiui: **1 backend + 1 Postgres + 1 statinė SPA**, EU regione, su HTTPS, slaptažodžių saugykla ir savaitinių/dieninių atsarginių kopijų istorija.

### 1a. Render.com (esamas RUNBOOK pasiūlymas)

| Pozicija | Kaina | Pastabos |
|---|---|---|
| Web Service Starter | **$7/mėn.** | 512 MB RAM, 0.5 CPU, visada paleistas |
| Postgres Basic-256MB | **$7/mėn.** | dieniniai backupai, 1 GB saugykla, +€0.30/GB |
| Static Site (frontend) | **$0** | neribota juosta praktiškai, integruoti CI builds |
| Workspace Hobby | $0 | (Pro = $19/user/mėn., bet beta nereikia) |

**Iš viso: ~$14/mėn. (~€13/mėn.)** ([Render Pricing](https://render.com/pricing), [Kuberns 2026 review](https://kuberns.com/blogs/render-pricing/))

- Regione: **Frankfurt** yra ([source](https://danubedata.ro/blog/render-com-alternatives-europe-2026)).
- Setup laikas: ~30 min nuo zero iki HTTPS.
- Backups: dieniniai automatiniai Postgres snapshotai. Point-in-time recovery — tik nuo $50+ planų.
- Free tier: web service yra, bet auto-suspend po 15 min idle (netinka).
- **Trūkumas:** US įmonė, CLOUD Act jurisdikcija ([source](https://danubedata.ro/blog/render-com-alternatives-europe-2026)). GDPR-wise duomenys EU, bet vyriausybinės užklausos teoriškai galimos.

### 1b. Fly.io

| Pozicija | Kaina | Pastabos |
|---|---|---|
| shared-cpu-1x 512MB VM | ~**$3.20/mėn.** | pay-as-you-go, sek. tarifu |
| **Managed Postgres Basic** | **$38/mėn.** | shared-2x, 1GB RAM ([source](https://fly.io/docs/mpg/)) |
| Static (Fly + Tigris arba kitur) | ~$0–5 | nera native static-site funkcijos |

**Iš viso: ~$41+/mėn.** Managed Postgres pajudino kainas virš mūsų biudžeto. ([Fly pricing](https://fly.io/docs/about/pricing/))

- Frankfurt + Amsterdamas yra.
- Setup sudėtingesnis (`flyctl`, `fly.toml`, Docker).
- **Workaround:** rinktis self-managed Postgres VM (~$3/mėn.), bet tada savininkas turi prižiūrėti backupus pats. Beta faze — ne.
- Naujiems klientams legacy free tier nebebėra ([Fly docs](https://fly.io/docs/about/pricing/)).

### 1c. Hetzner Cloud (EU pirmenybė)

| Pozicija | Kaina | Pastabos |
|---|---|---|
| CX22 (2 vCPU, 4GB) Helsinki | **€4.49/mėn. + PVM** | po 2026-04-01 kainų indeksavimo ([source](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)) |
| CPX11 (2 vCPU, 2GB) Falkenstein | **€5.49/mėn. + PVM** | x86 AMD |
| Managed Postgres | **nėra** ([source](https://danubedata.ro/blog/render-com-alternatives-europe-2026)) | reikia paleisti pačiam (Docker compose + pg_dumpall cron) |

**Iš viso: ~€5–6/mėn. + PVM**, BET reikia paties admin'o darbo (sistema su nginx, certbot, pg_dump cron, ufw, atnaujinimai). Dažnai ~2–4 val./mėn. priežiūros.

- Falkenstein, Nuremberg, Helsinki — visi EU.
- Vokiečių įmonė, EU jurisdikcija — geriausias GDPR atveju.
- **Trūkumas:** vienkartinis setup ~3–6 valandos. Backupai — Hetzner snapshots €0.011/GB/mėn., reikia rankiniu būdu. Kraštas nepriklausomas inžinieriaus laiko vertei.

### Rekomendacija: **Render.com**

Solo founder, beta per kelias dienas, ~10 vartotojų, kainos lubos €20/mėn. Render laimi todėl, kad:

1. **Time-to-deploy ~30 min**, ne kelios valandos. Hetzner sutaupytų ~€7/mėn., bet kainuotų ~6 val. setupo + nuolatinę priežiūrą. Per 2 mėn. tampi minus.
2. **Managed Postgres už €7/mėn.** — Fly.io nesutalpina (€38/mėn. minimum); Hetzner — DIY.
3. **Native static-site hostingas frontendui** — prijungtas prie repo, automatinis CI buildas, free.
4. **Rollback mygtuku** vienu paspaudimu (jau aprašyta RUNBOOK §8). Pirmąją savaitę tai svarbu.
5. **Frankfurt regionas** užtikrina ~30–50ms latency LT vartotojams.

**Migravimo planas, jei augs:** kai aktyvių vartotojų >100 ar API kaštai >€100/mėn., persikelti backendą į Hetzner CX22 + self-managed Postgres su Ubicloud arba Elestio. Tada DevOps darbas atsiperka.

> Render = 80/20 sprendimas šiandienai. Ne galutinis stack.

---

## 2. Domenas + DNS

Pathon valdo `pathon.eu` per LT registrarą (greičiausiai `domains.lt` arba `iv.lt`). Mes pridedame `samatu.pathon.eu` subdomeną. **Apex domenas neliečiamas** — Pathon koroporatyvinė svetainė lieka kur buvusi.

### 2.1 Architektūros pasirinkimas

Du variantai:

- **A (rekomenduoju):** `samatu.pathon.eu` rodo į frontend (statinis SPA); `samatu-api.pathon.eu` rodo į backend. Aiški separacija, paprastas CORS.
- **B:** vienas hostas, backend reverse-proxina frontend. Daugiau konfigūracijos, mažiau lankstu.

Rinkmės A.

### 2.2 Cloudflare priekyje (free tier)

**Kodėl Cloudflare:** DDoS apsauga free, auto-TLS edge cache (TLS 1.3), HTTP/3, slaptas origin IP, cache statiniams asetams. Origin pas Render gauna mažiau hits ⇒ tariama mažesnė pastovios apkrovos kaina.

**Žingsniai:**

1. `cloudflare.com` → susikurk free account su Pathon Google login.
2. **Add Site → `pathon.eu`** → Free plan. Cloudflare nuskenuos esamus DNS recordus.
3. **NEPERKELK nameserverių** į Cloudflare (Pathon korporatyvinės svetainės nesugadinkim). Vietoj to naudok **Partial CNAME setup** ([Cloudflare docs](https://developers.cloudflare.com/dns/zone-setups/partial-setup/)) — Cloudflare dirbs tik mūsų subdomenui.

Jei partial setup neprieinamas free tieryje (kartais reikia Business), alternatyva: deleguok subdomeną į Cloudflare nameserverius:
   ```
   samatu.pathon.eu  NS  ns1.cloudflare.com
   samatu.pathon.eu  NS  ns2.cloudflare.com
   ```
ir pridėk `_pathon.eu` zoną Cloudflare'e tik subdomeno valdymui.

4. **DNS recordai Cloudflare'e** (po deleguotos zonos):
   ```
   samatu       CNAME  samatu-frontend.onrender.com    Proxied (oranžinė debesylė)
   samatu-api   CNAME  samatu-backend.onrender.com     Proxied
   ```
5. **SSL/TLS → Overview → Full (strict)**. Render išduoda valid Let's Encrypt origin sertifikatą, todėl strict veiks ([Cloudflare community](https://community.cloudflare.com/t/setting-up-full-strict-ssl-tls-encryption/226809)).
6. **SSL/TLS → Edge Certificates → Always Use HTTPS = ON**, **Min TLS Version = 1.2**, **Automatic HTTPS Rewrites = ON**.
7. **Speed → Optimization → Brotli = ON** statiniams asetams.
8. Render dashboarde abiem servisams pridėk custom domain `samatu.pathon.eu` ir `samatu-api.pathon.eu`. Render išduos Let's Encrypt sertifikatą (5–15 min).

### 2.3 DMARC + SPF + DKIM — apsauga nuo abuse-bill spoofingo

**Grėsmė konkrečiai:** Spamerai gali pasiųsti milijonus laiškų `@pathon.eu` ar `@samatu.pathon.eu` adresu. Be DMARC `p=reject`:

- Bouncebackai grįžta į pristatomus (catch-all) inboxus → Postmark/Resend bills augs jei vėliau prijungsi.
- Reputacija krenta — tikri laiškai (slaptažodžio resetas) atsiduria spam'e.
- Phishing rizika klientams ("DanubeData padidino kainas" laiško pavyzdys).

**Mitigation = trio rekordai apaše + null MX subdomenui** ([dmarc.org](https://dmarc.org/), [Cloudflare guide](https://www.cloudflare.com/learning/dns/dns-records/protect-domains-without-email/)).

**Subdomenui `samatu.pathon.eu` (kuris NEsiunčia paštu pirmąjame etape):**

```dns
; SPF — niekas negali siųsti šio domeno vardu.
samatu.pathon.eu.       TXT   "v=spf1 -all"

; DMARC — reject visi laiškai kurie sufaileina SPF/DKIM.
_dmarc.samatu.pathon.eu. TXT  "v=DMARC1; p=reject; rua=mailto:dmarc@pathon.eu; ruf=mailto:dmarc@pathon.eu; adkim=s; aspf=s; fo=1"

; Null MX (RFC 7505) — aiškus signalas: šis domenas pašto nepriima.
samatu.pathon.eu.       MX 0  "."
```

**Apex `pathon.eu` (jei dar nesutvarkyta, BŪTINA pridėti):**

```dns
; Jei apex jau siunčia paštu (pvz. per Google Workspace), pradėk nuo p=none ir 2 sav. stebėk rua reportus, tada pereik į p=quarantine, vėliau p=reject.
_dmarc.pathon.eu.       TXT   "v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@pathon.eu; ruf=mailto:dmarc@pathon.eu; adkim=s; aspf=s; sp=reject; fo=1"

; SPF — leisk tik tikriems siuntejams (pvz. Google, Resend). Jei nesiunčia — '-all'.
pathon.eu.              TXT   "v=spf1 include:_spf.google.com -all"

; DKIM — Google Workspace generuoja `google._domainkey.pathon.eu`. Resend duos `resend._domainkey`.
google._domainkey.pathon.eu. TXT "v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBA..." (paste'ink iš provider'io)
```

**Kiekvienas rekordas — kodėl:**

| Rekordas | Funkcija | Kaina jei nepridėsi |
|---|---|---|
| `SPF -all` | Vienintelis sąrašas leidžiamų IP. `-all` = "viskas kita reject". | Spamer'is iš bet kur gali sufalsifikuoti `noreply@samatu.pathon.eu`. |
| `DKIM` | Cryptographically signed `From:` header. Privalomas Gmail/Yahoo bulk senders politikos. | Tikri laiškai eis į spam. |
| `DMARC p=reject` | Komanda receivers'iams: jei SPF arba DKIM faileina, **mesk**, ne quarantine. | Spamer'iai tęsia, tu mokėsi už bouncebackus. |
| `rua=...` | Aggregate reportai (XML, dieniniai) — kas siunčia tavo vardu. | Nematau atakų istorijos. |
| `MX "."` | Null MX — domain nereceives mail. Aiškus reject signalas mail server'iui. | Spamer'iai bandys deliver fake admin@... |

**Stebėjimas:** užsiregistruok free `dmarc.postmarkapp.com` arba `dmarcdigests.com` — agreguoja `rua=` XML reportus į readable savaitės summary. Pirmas mėnuo lemiamas.

> Šaltinis: [DMARCLY guide](https://dmarcly.com/blog/how-to-implement-dmarc-dkim-spf-to-stop-email-spoofing-phishing-the-definitive-guide), [Cloudflare email security](https://www.cloudflare.com/learning/email-security/dmarc-dkim-spf/), [Google DMARC setup](https://support.google.com/a/answer/2466580).

---

## 3. Landing puslapio sprendimas

Trys variantai, lyginant solo founder pre-launch kontekstui:

### 3a. Esamas in-app `Landing.jsx`

| Kriterijus | Įvertinimas |
|---|---|
| Build laikas | 0 (jau yra) |
| Maintenance | Maišosi su app code. Kiekvienas marketing'o copy fix = git commit + deploy |
| SEO | Vidutinis. Vite SPA — turinys kraunasi po JS, Googlebot dabar dažniausiai render'ina, bet hreflang/structured data reikalauja extra darbo |
| A/B testing | Sunku — feature flags arba reload |
| Cost | €0 (jau host'inta su SPA) |

### 3b. Webflow / Framer / Carrd ant atskiro hosto

| Kriterijus | Įvertinimas |
|---|---|
| Build laikas | 4–8 val. (visual editor learning curve) |
| Maintenance | Designer-friendly, nereikia deploy |
| SEO | Geras — server-rendered HTML, native sitemap |
| A/B testing | Webflow: Optimize integration; Framer: native variants |
| Cost | Carrd $19/year (apex domain), Framer $5/mo, Webflow $14/mo (CMS) |

Architektūra: `samatu.pathon.eu` = marketingas (Framer/Carrd); `app.samatu.pathon.eu` = app. Aiškus split.

### 3c. Astro/Next.js statinis landing co-located su app

| Kriterijus | Įvertinimas |
|---|---|
| Build laikas | 8–16 val. (setup + content + design tokens reuse) |
| Maintenance | Code, ne UI. Reikia git skill vienoms copy edits |
| SEO | Geriausias — full SSR/SSG, total control |
| A/B testing | Reikia self-implement (Vercel Analytics + Splitbee, etc.) |
| Cost | €0 (host'as kartu) |

### Rekomendacija: **3a (esamas Landing.jsx) iki ~50 vartotojų**

Argumentai:

1. Jau veikia. Pre-launch — laikas ne marketing perfection, bet product validation.
2. SEO beta fazei nesvarbu — vartotojai ateina per 1-on-1 outreach, ne per Google.
3. A/B testas su 10 vartotojais statistically meaningless. Atidėk.
4. **Migration trigger:** kai turėsi >100 active users + paid tier žinia, persikelk į **3b (Framer)** atskirai. Designer pieš, tu deploy'insi `app.samatu.pathon.eu`. Apex `samatu.pathon.eu` pajudės į Framer.

**Trumpas patarimas:** dabar `Landing.jsx` papildyk:
- `<title>` ir `<meta description>` lietuviškai per `react-helmet-async` arba native `useEffect document.title`.
- `<link rel="canonical">` į `https://samatu.pathon.eu/`.
- `og:image` 1200×630 PNG (vienkartinis Figma export).
- `robots.txt` allow visus, `sitemap.xml` su 1 URL.

Dažna klaida: Landing su React-router → atviri tabai grįžta į login, ne hero. Sutvarkyk `index.html` redirect arba `<Routes>` viršuje su `<Route path="/" element={<Landing/>}>`.

---

## 4. Aplinkos kintamieji + slaptažodžiai

### 4.1 Generuoti `SAMATU_SECRET_KEY`

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Output ~64 simboliai. **Niekur necommit'ink.** Įdėk į Render env panel (žr. 4.3).

### 4.2 Anthropic API key + monthly cap

1. https://console.anthropic.com/settings/keys → **Create Key** → pavadink `samatu-prod-2026-05`. Nukopijuok `sk-ant-api03-...` reikšmę (rodoma vieną kartą).
2. https://console.anthropic.com/settings/limits → kairiajame meniu **Limits** → **Monthly spend limit** → įvesk **$100**. Tai įmonės-lygio cap.
3. Jei per console matomas "Workspaces" — sukurk atskirą workspace `samatu-prod`, su atskira cap'a. Beta limit: $50/mėn., production: $200/mėn.
4. Spending alerts: 50%, 80%, 100% — el. paštu.

> Jei nėra screenshot, vizualiai: kairysis sidebar → "Settings" → "Limits" → "Monthly spend limit" laukas su € žymeliu. "Save" mygtukas po lauku. Setting taikomas visiems organization keys.

**Antras saugiklis app lygmenyje:** `SAMATU_USER_DAILY_SPEND_EUR=0.50` (pagal RUNBOOK §4) — bet kuris vienas vartotojas neviršys $0.50/dieną. Jei 10 vartotojų × $0.50 × 30 dienų = $150/mėn. teorinis maksimumas. Anthropic cap = hard wall.

### 4.3 Slaptažodžių saugykla Renderyje

Render Dashboard → **samatu-backend service → Environment** → **Add Environment Variable**.

```
ANTHROPIC_API_KEY            sk-ant-...                  (Secret = ✓)
SAMATU_SECRET_KEY            <token_urlsafe output>      (Secret = ✓)
ENV                          production
SAMATU_CORS_ORIGINS          https://samatu.pathon.eu
SAMATU_USER_DAILY_SPEND_EUR  0.50
SAMATU_USER_HOURLY_EXTRACTS  10
SAMATU_DB_PATH               /data/samatu.db
GOOGLE_CLIENT_ID             <vėliau, jei naudosi>
GOOGLE_CLIENT_SECRET         <vėliau>
GOOGLE_REDIRECT_URI          https://samatu-api.pathon.eu/api/auth/google/callback
```

**Persistencija:** Render → **Disks** → Add Disk `/data` 1 GB ($0.25/GB/mėn. = $0.25) — kelias privalo sutapti su `render.yaml` disko `mountPath` ir `SAMATU_DB_PATH`. Ten gulės SQLite. Jei vėliau migruosim į Postgres, šis diskas tampa nereikalingas.

**Frontend env (Static Site → Environment):**
```
VITE_BACKEND_URL  https://samatu-api.pathon.eu
```

### 4.4 Slaptažodžių rotacija nelaužant sesijų

Pagal `docs/SECURITY.md` §"Rotation runbook":

- **`SAMATU_SECRET_KEY` rotacija = ALL sessions invalid.** Tai _by design_ (kompromituoto rakto atveju). Praktiškai: paskelbk vartotojams 24h iš anksto el. paštu / Slack'e, atlik darbo dienos pabaigoje.
- **`ANTHROPIC_API_KEY` rotacija** sesijų neliečia. Procesas:
  1. Anthropic console → Create Key → naują pavadink `samatu-prod-2026-XX`.
  2. Render env → atnaujink `ANTHROPIC_API_KEY` reikšmę → **Save Changes** (Render automatiškai redeploy ~30 s).
  3. Patikrink `/v9/symbols/detect` POST endpoint'ą su test PDF'u — jei 200 OK, working.
  4. Anthropic console → senas raktas → **Revoke**.
- **Google OAuth secret rotacija**: Google Cloud → Credentials → Reset secret → atnaujink env → redeploy. Vartotojai neatsijungia, nes session cookie nepriklauso nuo OAuth secret.

**Saugiklis:** prieš rotuojant `SAMATU_SECRET_KEY`, eksportuok aktyvių sesijų skaičių (`SELECT COUNT(*) FROM sessions WHERE expires_at > now();`) — žinosi mastą.

---

## 5. Pre-launch smoke checklist (15 žingsnių)

Pakeisk `samatu.pathon.eu` jei naudoji kitą host'ą. Visi `curl -i` rodo headerius — **patikrink `Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options: DENY`** kiekviename API atsakyme.

```bash
# 1. DNS resolves correctly
dig +short samatu.pathon.eu
dig +short samatu-api.pathon.eu
# expect: Cloudflare proxy IPs (104.21.x.x or 172.67.x.x)

# 2. HTTPS works, valid cert
curl -I https://samatu.pathon.eu/
# expect: HTTP/2 200, Server: cloudflare

# 3. HTTP redirects to HTTPS
curl -I http://samatu.pathon.eu/
# expect: 301 → https://...

# 4. Frontend loads, has correct title
curl -s https://samatu.pathon.eu/ | grep -i '<title>'
# expect: <title>Sąmatų AI...</title>

# 5. Backend health endpoint
curl -i https://samatu-api.pathon.eu/api/health
# expect: 200, JSON {"status": "ok"}

# 6. Backend security headers (production)
curl -I https://samatu-api.pathon.eu/api/health | grep -iE 'strict-transport|content-security|x-frame|x-content-type|referrer-policy|permissions-policy'
# expect: VISI 6 headeriai

# 7. CORS allows tik mūsų origin'ą
curl -i -X OPTIONS https://samatu-api.pathon.eu/api/auth/login \
  -H 'Origin: https://samatu.pathon.eu' \
  -H 'Access-Control-Request-Method: POST'
# expect: Access-Control-Allow-Origin: https://samatu.pathon.eu

# 8. CORS BLOKUOJA piktos kilmes
curl -i -X OPTIONS https://samatu-api.pathon.eu/api/auth/login \
  -H 'Origin: https://evil.example.com' \
  -H 'Access-Control-Request-Method: POST'
# expect: NĖRA Access-Control-Allow-Origin header'io, ARBA 403

# 9. Auth-required endpoint blocks anonymous
curl -i -X POST https://samatu-api.pathon.eu/extract -F 'file=@/dev/null'
# expect: 401 Unauthorized arba 403

# 10. Register naują test user (browser arba curl)
curl -i -X POST https://samatu-api.pathon.eu/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"smoke-test@pathon.eu","password":"Test12345!"}' \
  -c /tmp/samatu-cookies.txt
# expect: 200, Set-Cookie: samatu_session=...; HttpOnly; Secure; SameSite=Lax

# 11. Patvirtink cookie flag'us
grep samatu_session /tmp/samatu-cookies.txt
# expect: 'HttpOnly' + 'Secure' rows

# 12. Logged-in endpoint reaguoja
curl -b /tmp/samatu-cookies.txt -i https://samatu-api.pathon.eu/api/auth/me
# expect: 200, {"email":"smoke-test@pathon.eu", ...}

# 13. Rate limit veikia (auth-mutating)
for i in {1..35}; do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST https://samatu-api.pathon.eu/api/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"email":"x@x.com","password":"x"}'
done | sort | uniq -c
# expect: matysis 429 atsakymų po ~30 bandymų

# 14. PDF upload size limit
dd if=/dev/zero of=/tmp/big.pdf bs=1M count=210
curl -b /tmp/samatu-cookies.txt -i -X POST https://samatu-api.pathon.eu/extract \
  -F 'file=@/tmp/big.pdf'
# expect: 413 Payload Too Large

# 15. Real PDF extract end-to-end
curl -b /tmp/samatu-cookies.txt -X POST https://samatu-api.pathon.eu/extract-interior \
  -F 'file=@backend/test_pdfs/p1.pdf' \
  -w "\nTime: %{time_total}s\n"
# expect: 200, JSON su rooms[], <30s response time
```

**Po 15 žingsnių:** atidaryk browser DevTools → Application → Cookies → patikrink `samatu_session` flag'us vizualiai. Network tab'e — pirmas request'as turi `Strict-Transport-Security` ir CSP. Console — jokių mixed content warning'ų.

---

## 6. Email service — alternatyvos Postmark $10/mėn.

Vartotojas explicit'ai paprašė research'inti. Beta fazei email reikalingas tik **password reset**'ui (kitos transactional ne yra esential). Dabartinis status: nėra prijungta, registracija įmanoma, password reset disabled.

| Servisas | Free tier | Paid start | Deliverability | Setup |
|---|---|---|---|---|
| **Resend** | **3,000/mėn., 100/dieną**, 1 custom domain ([source](https://resend.com/pricing)) | $20/mėn. už 50,000 | Aukšta (komanda iš ex-Postmark) | API + DKIM, ~15 min |
| Mailtrap | 1,000/mėn. transactional | $15/mėn. | Vidutinė; populiaresnis testavimui | API/SMTP |
| **AWS SES** | $0.10 / 1,000 emails — t.y. **$0.001 už 10 laiškų** ([source](https://aws.amazon.com/ses/pricing/)) | Pay-as-you-go | Aukšta, jei DKIM+DMARC tvarka | Sudėtingas setup, sandbox 200/dieną kol nepatvirtins ([AWS docs](https://docs.aws.amazon.com/ses/latest/dg/manage-sending-quotas.html)) |
| Postal (self-hosted) | Tik VM cost (~€5) | — | Priklauso nuo IP reputacijos | Kelios valandos, plus IP warmup savaitės |
| Postmark | $15/mėn. už 10,000 (be free tier) | — | Geriausia industriajoje | API, paprastas |

### Rekomendacija: **Resend**

Argumentai:
1. **3,000/mėn. free** = ~100/dieną. Beta su 10 vartotojų, password reset < 5/dieną → metai be sąskaitos.
2. Setup laikas trumpiausias — Resend API dabar de facto standartas (į ją migravo nemažai SaaS'ų po Postmark kainų augimo 2025).
3. LT deliverability: testai rodo Resend rezultatus su `@gmail.com`, `@yahoo.com`, `@inbox.lt`, `@delfi.lt` analogiškus Postmark.
4. **Free tier custom domain** — gali siųsti `noreply@samatu.pathon.eu` (svarbu DMARC alignment'ui — `aspf=s` strict mode).

**AWS SES vertas dėmesio kai vartotojų >500** — €0.10 už 1k yra 10× pigiau nei Resend paid tier. Bet beta — laiko vertė >> €5/mėn. taupymas.

**Ne urgent:** RUNBOOK §"Decisions deferred" sako tikrąjį dalyką — beta gali leist registruotis be password reset. **Pridėk Resend kai prireiks pirmojo "pamiršau slaptažodį" žodžio support'e.** Nepradėk kuriant integraciją prieš laiką.

---

## 7. Rizikų registras (top 5 per pirmas 7 dienas)

| # | Rizika | Tikimybė | Poveikis | Mitigacija |
|---|---|---|---|---|
| **1** | **Anthropic API ištaupo biudžetą** dėl extract'ų ciklo / paranojos vartotojų | Vidutinė | Aukštas (€100+ savaitės) | (a) `SAMATU_USER_DAILY_SPEND_EUR=0.50` jau yra; (b) Anthropic console hard cap $50/mėn. beta; (c) dieninis cron `/api/admin/stats` patikrinimas; (d) Sentry alert ant `429` arba `502` iš Anthropic |
| **2** | **DMARC/SPF nesutvarkyta** → spamer'is pasiūnčia 100k laiškų `@samatu.pathon.eu` → Pathon apex reputacija krenta | Vidutinė | Aukštas (kitos Pathon paslaugos pradeda eit į spam) | §2.3 trio rekordai (SPF -all, DMARC p=reject, null MX) deploy'inti **PRIEŠ** paskelbiant |
| **3** | **Cloudflare cache'ina backend API** → vartotojai mato senus duomenis arba kitų user'ių session | Maža | Kritinis | (a) Cloudflare → Caching Rules → bypass cache visiems `/api/*` ir `/extract*` URI; (b) backend headeris `Cache-Control: no-store` auth-required endpoint'uose (jau yra `_auth.require_user`); (c) test step §5.10 (login) — patikrink Cookie nesistore'inta |
| **4** | **Render starter instance crash** (OOM iš 512 MB) per Vision pipeline'ą su didesniu PDF'u | Aukšta | Vidutinis (downtime kol restart'inasi ~60s) | (a) `MemoryWatchdog` jau auto-resetina >500 MB heap (žr. `git log` sprint-1); (b) upload size cap 200 MB (yra); (c) Render Health Check on `/api/health`; (d) jei kartojasi — upgrade į $25/mėn. Standard 2GB RAM |
| **5** | **GDPR DSAR** užklausa pirmąją savaitę (vartotojas nori savo duomenų) | Maža | Vidutinis (2–4 val. darbo) | (a) Privacy policy page nurodo 30 dienų SLA (ne 24h); (b) `backend/api/admin/export-user.py` skriptas paruoštas (jei dar nera, parašyk MVP versiją šio sprint'o); (c) Render Postgres dump → CSV iš `users`/`projects` lentelių per `pg_dump --table` |

**Bonus rizika #6 (mažesnė):** Hetzner kainų indeksavimas užfiksavo 30% padidėjimą 2026-04-01 ([source](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)). Jei migruosim ten Q3'26, tikrink up-to-date kainas — nepasikliauk šiuo dokumentu.

---

## Launch day timeline (start = 09:00 LT)

| Laikas | Veiksmas | Trukmė | Kontrolės taškas |
|---|---|---|---|
| **08:30** | Kava. `git pull main`. `git log` patikrint paskutinis commit hash | 15 min | Žinai būseną |
| **08:45** | Lokali smoke: `cd backend && uvicorn main:app --port 8000`; `cd frontend && npm run build && npm run preview`; pakeisk `.env` į ENV=production | 30 min | Veikia local'iai |
| **09:15** | Render dashboard → Manual Deploy backend ir frontend (Latest commit) | 5 min push, ~5 min build | Build green abiems |
| **09:25** | Stebėk Render → Logs realtime — uvicorn startas turi rodyt `Application startup complete`, jokios `ANTHROPIC_API_KEY missing` warning | 5 min | Backend ready |
| **09:30** | Cloudflare DNS aktyvink (CNAME proxied). `dig samatu.pathon.eu` patikrink resolve | 5 min DNS, 0–10 min propagacija | Resolves į CF IPs |
| **09:40** | SSL — Render išduos LE cert. Cloudflare → SSL/TLS = Full (Strict) | ~10 min wait | Browser rodo žaliai padlock |
| **09:50** | Smoke checklist §5 visi 15 žingsnių iš laptop terminal'o | 30 min | Visi green |
| **10:20** | DMARC/SPF/MX recordai į registrarą (jei dar ne) | 15 min | `dig TXT _dmarc.samatu.pathon.eu` rodo p=reject |
| **10:35** | Browser test: register → upload test PDF → check admin panel | 20 min | E2E veikia |
| **10:55** | Skaitiklių baseline'as: Render dashboard tab'ai (CPU, RAM, requests) atviri kaip browser tabai. Anthropic console — Usage tab atviras. UptimeRobot pridėk monitor'ą `https://samatu.pathon.eu` ir `https://samatu-api.pathon.eu/api/health` (5 min interval) | 20 min | Monitoringas live |
| **11:15** | **PRANEŠIMAS BETA TESTUOTOJAMS.** El. laiškas / Slack DM 5 žmonėms. Linkas + login instrukcijos | 15 min | Pirmieji vartotojai užregistruoti |
| **11:30 → 17:00** | **Stebėk.** Kas 60 min: Render logs (errors), Anthropic spend, browser refresh `/admin`. Pirma valanda — likti laptop priekyje, ne video calls | 5.5 val. | <5% error rate |
| **17:00** | Day-1 retrospektyva: kiek vartotojų užregistrųvo, kiek extracts, kiek $ Anthropic spent. Įrašyk į `docs/launch-day-2026-XX-XX.md` | 30 min | Aiški base'as 2-rai dienai |

**Stop conditions** — sustabdyk launch'ą jei:
- Smoke step §5.10 fails (auth broken) → rollback
- §5.6 trūksta CSP arba HSTS header'io → ENV=production env var blogai
- Anthropic spend per pirmas 30 min > $5 → kažkas DDoS'ina extract endpoint'ą; suspensk service, debug

---

## Tikrinami šaltiniai

Kainos ir feature'ai keičiasi. Patikrink šituos URL'us prieš darant pirkimą:

- **Render pricing** — https://render.com/pricing
- **Render Postgres pricing/limits** — https://render.com/docs/postgresql-refresh + https://kuberns.com/blogs/render-postgres-pricing-setup-limits/
- **Render alternatives EU GDPR** — https://danubedata.ro/blog/render-com-alternatives-europe-2026
- **Fly.io pricing** — https://fly.io/docs/about/pricing/
- **Fly.io Managed Postgres** — https://fly.io/docs/mpg/ + https://community.fly.io/t/managed-postgres-pricing/25734
- **Fly.io MPG inter-region charges 2026-02** — https://community.fly.io/t/we-are-going-to-start-charging-for-mpg-inter-region-private-network-usage-from-febuary-2026/26561
- **Hetzner Cloud regular performance** — https://www.hetzner.com/cloud/regular-performance
- **Hetzner Cloud cost-optimized (CX series)** — https://www.hetzner.com/cloud/cost-optimized
- **Hetzner price adjustment 2026-04-01** — https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
- **Hetzner Cloud review benchmarks** — https://betterstack.com/community/guides/web-servers/hetzner-cloud-review/
- **Railway pricing** — https://railway.com/pricing + https://docs.railway.com/pricing/plans
- **Resend pricing** — https://resend.com/pricing
- **AWS SES pricing** — https://aws.amazon.com/ses/pricing/
- **AWS SES sandbox limits** — https://docs.aws.amazon.com/ses/latest/dg/manage-sending-quotas.html
- **DMARC.org overview** — https://dmarc.org/
- **DMARC implementation guide (DMARCLY)** — https://dmarcly.com/blog/how-to-implement-dmarc-dkim-spf-to-stop-email-spoofing-phishing-the-definitive-guide
- **Cloudflare email security** — https://www.cloudflare.com/learning/email-security/dmarc-dkim-spf/
- **Cloudflare protect non-sending domains** — https://www.cloudflare.com/learning/dns/dns-records/protect-domains-without-email/
- **Cloudflare DNS partial setup (CNAME)** — https://developers.cloudflare.com/dns/zone-setups/partial-setup/
- **Cloudflare SSL Full (Strict)** — https://community.cloudflare.com/t/setting-up-full-strict-ssl-tls-encryption/226809
- **Google DMARC setup** — https://support.google.com/a/answer/2466580
- **Microsoft DMARC docs** — https://learn.microsoft.com/en-us/defender-office-365/email-authentication-dmarc-configure
- **RFC 7505 (Null MX)** — https://datatracker.ietf.org/doc/html/rfc7505
- **Anthropic Console (key + limits)** — https://console.anthropic.com/settings/keys + https://console.anthropic.com/settings/limits

---

## Priedas: vidinis decision log

| Klausimas | Sprendimas | Data | Pagrindimas |
|---|---|---|---|
| Hostas | Render.com Frankfurt | 2026-05-05 | Time-to-deploy + managed Postgres €7 + native static site |
| CDN/proxy | Cloudflare Free | 2026-05-05 | DDoS shield + edge TLS, free, partial CNAME setup |
| Landing | In-app Landing.jsx | 2026-05-05 | Beta fazei pakanka; migration trigger = >100 MAU |
| Email | Atidėta iki password reset reikalavimo | 2026-05-05 | Resend free tier, kai prireiks |
| DB | Render Postgres Basic-256MB | 2026-05-05 | $7/mėn. + dieniniai backupai |
| Storage | Render Disk 1 GB ($0.25) | 2026-05-05 | SQLite fallback jei Postgres nesutalpina |
| Monitoring | UptimeRobot free + Render Logs | 2026-05-05 | Sentry pridėsim po pirmo crash |

> Šis dokumentas — gyvas. Atnaujink po pirmojo deploy'o realiomis URL'ais ir IP'ais.
