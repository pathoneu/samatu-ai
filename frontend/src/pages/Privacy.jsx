/**
 * Privacy — privatumo politika (LT, GDPR-grindžiama).
 * Static page; for production launch consult lawyer to refine wording.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

export default function Privacy() {
  return (
    <div className="min-h-screen p-6 bg-background">
      <div className="max-w-3xl mx-auto">
        <Link to="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6">
          <ArrowLeft className="w-4 h-4" /> Grįžti
        </Link>
        <article className="prose prose-neutral dark:prose-invert max-w-none">
          <h1>Privatumo politika</h1>
          <p className="text-sm text-muted-foreground">Atnaujinta: 2026-04-27</p>

          <h2>Kas mes esame</h2>
          <p>
            Sąmatų AI — Lietuvoje veikianti vidaus apdailos sąmatų skaičiavimo
            paslauga. Toliau "mes" arba "Sąmatų AI". Kontaktai: solutions@pathon.eu.
          </p>

          <h2>Kokius duomenis renkame</h2>
          <ul>
            <li><strong>Paskyros duomenys</strong>: el. paštas (privaloma), vardas, įmonės pavadinimas (neprivaloma).</li>
            <li><strong>Slaptažodis</strong>: saugomas vienakrypčiu bcrypt hash'u — niekada nesaugomas atviru tekstu, niekada nematomas net administratoriams.</li>
            <li><strong>Projektų duomenys</strong>: jūsų įkelti PDF brėžiniai ir AI ištrauktos sąmatos. Saugomi mūsų serveryje, susiję su jūsų paskyra.</li>
            <li><strong>Naudojimo statistika</strong>: kada įkėlėte projektą, kiek kambarių, kainos sąnaudos. Naudojama paslaugos kokybei pagerinti.</li>
            <li><strong>Korekcijų žurnalas</strong>: kai pakeičiate AI rezultatus (pvz. "drabužinės nedažomos"), saugome lauko pavadinimą + senąją/naująją reikšmę. Naudojama AI promptų tobulinimui — niekuomet neperduodama tretiesiems asmenims.</li>
            <li><strong>Sesijos slapukas</strong>: vienas HTTPOnly slapukas (pavadinimas <code>samatu_session</code>) prisijungimo būsenai išlaikyti. Neturi reklamos ar trečiųjų šalių sekimo.</li>
          </ul>

          <h2>Kam naudojame duomenis</h2>
          <ul>
            <li>Paslaugos teikimui (sąmatų generavimui, projektų saugojimui)</li>
            <li>Paskyros valdymui ir komunikacijai (techniniai pranešimai)</li>
            <li>Paslaugos kokybės gerinimui (statistinė analizė, AI promptų tobulinimas)</li>
            <li>Saugumui (rate limit, fraud detection)</li>
          </ul>

          <h2>Kas turi prieigą prie duomenų</h2>
          <ul>
            <li>JŪS — savo projektai pasiekiami tik per jūsų paskyrą.</li>
            <li>Mūsų administratoriai — gali peržiūrėti agreguotą statistiką ir techniniam palaikymui.</li>
            <li>Anthropic (AI tiekėjas) — kai įkeliate PDF, jis siunčiamas Anthropic Claude API analizei. Anthropic įsipareigoja per 30 dienų ištrinti API duomenis ir nenaudoja jų modeliui treniruoti. Žiūrėkite: <a href="https://www.anthropic.com/legal/privacy" target="_blank" rel="noopener">anthropic.com/legal/privacy</a>.</li>
          </ul>

          <h2>Kiek laiko saugome</h2>
          <ul>
            <li>Aktyvios paskyros: kol egzistuoja paskyra.</li>
            <li>Ištrintos paskyros: 30 dienų soft-delete, tada visiškas ištrynimas.</li>
            <li>Korekcijų žurnalas: agreguotas, anonimizuotas — saugomas neribotai (statistinė analizė).</li>
            <li>Serverio žurnalai (su IP): 90 dienų.</li>
          </ul>

          <h2>Jūsų teisės (GDPR)</h2>
          <ul>
            <li><strong>Prieiga</strong>: galite peržiūrėti visus savo duomenis pagrindiniame puslapyje.</li>
            <li><strong>Eksportas</strong>: kiekvieną projektą galite eksportuoti į Excel/PDF.</li>
            <li><strong>Ištrynimas</strong>: galite ištrinti projektus arba paskyrą savarankiškai. Norėdami ištrinti — susisiekite solutions@pathon.eu.</li>
            <li><strong>Skundas</strong>: turite teisę skųstis Valstybinei duomenų apsaugos inspekcijai (vdai.lrv.lt).</li>
          </ul>

          <h2>Saugumas</h2>
          <p>
            Slaptažodžiai saugomi bcrypt hash'u (work factor 12). Jungtys per HTTPS.
            Sesijos slapukas yra HTTPOnly + SameSite=Lax, signature'd įraše. Reguliarūs
            saugumo atnaujinimai. Tačiau jokia sistema nėra 100% saugi — naudokite
            tvirtus slaptažodžius ir nedalinkitės jais.
          </p>

          <h2>Slapukai</h2>
          <p>
            Naudojame VIENĄ slapuką: <code>samatu_session</code> — prisijungimo
            būsenai. Tai vadinamasis "esminis" slapukas, kuriam GDPR sutikimas
            nereikalingas pagal LT teisę. Reklamos ar tracking slapukų nėra.
          </p>

          <h2>Pakeitimai</h2>
          <p>
            Atnaujinę šią politiką, pranešime el. paštu ir per programą. Esminiai
            pakeitimai įsigalios praėjus 30 dienų po pranešimo.
          </p>

          <p className="text-sm text-muted-foreground mt-8">
            Klausimai? <a href="mailto:solutions@pathon.eu">solutions@pathon.eu</a>
          </p>
        </article>
      </div>
    </div>
  );
}
