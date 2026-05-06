/**
 * Privacy — privatumo politika (LT, GDPR pagrįsta).
 *
 * 2026-05-06: išplėsta su duomenų valdytojo identifikacija, GDPR teisinio
 * pagrindo nuoroda (BDAR Art. 6), perdavimo už ES ribų sąlyga
 * (Anthropic — JAV), pažeidimų pranešimo prievolė. Prieš oficialų launch'ą
 * patikrinti su LT teisininku.
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
          <p className="text-sm text-muted-foreground">Atnaujinta: 2026-05-06 · Įsigalioja: 2026-05-06</p>

          <h2>1. Duomenų valdytojas</h2>
          <p>
            Šią paslaugą tiekia <strong>Pathon, MB</strong> (toliau — „Sąmatų AI",
            „mes" arba „mūsų"). Įmonės kodas: registruojama LT registrų centre.
            Kontaktai duomenų klausimais: <a href="mailto:solutions@pathon.eu">solutions@pathon.eu</a>.
          </p>
          <p>
            Ši politika paaiškina, kaip mes renkame, naudojame, saugome ir saugome
            jūsų asmens duomenis pagal Bendrąjį duomenų apsaugos reglamentą (BDAR /
            GDPR — 2016/679) ir Lietuvos Respublikos Asmens duomenų teisinės
            apsaugos įstatymą.
          </p>

          <h2>2. Kokius duomenis renkame</h2>
          <h3>2.1 Paskyros duomenys</h3>
          <ul>
            <li><strong>El. paštas</strong> (privaloma) — tapatybei nustatyti ir techninei komunikacijai.</li>
            <li><strong>Vardas / pavardė</strong> (neprivaloma) — pasiūlymų personalizavimui.</li>
            <li><strong>Įmonės pavadinimas</strong> (neprivaloma) — eksportuojamuose dokumentuose.</li>
            <li><strong>Slaptažodis</strong> — saugomas vienakrypčiu bcrypt maišomuoju (work factor 12).
              Atviro teksto slaptažodis NĖRA saugomas niekada — net administratoriai jo negali matyti.
              Pamiršus, slaptažodį atstatyti galima tik el. paštu su patvirtinimu.</li>
            <li><strong>Google paskyros duomenys</strong> — jeigu prisijungiate per Google OAuth,
              gauname jūsų Google paskyros: stabilų ID (`sub`), el. paštą, vardą ir avatar URL.
              Kitos Google paskyros informacijos nematome.</li>
          </ul>

          <h3>2.2 Projektų duomenys</h3>
          <ul>
            <li><strong>Įkelti PDF brėžiniai</strong> — saugomi serveryje, susiję tik su jūsų paskyra.
              Niekas kitas (išskyrus mūsų administratorius esant techniniam poreikiui) jų nemato.</li>
            <li><strong>AI ištrauktos sąmatos</strong> — patalpos, kiekiai, pozicijos.
              Saugomi šifruotoje duomenų bazėje (per HTTPS pasiekiama).</li>
            <li><strong>Įvestos kainos</strong> ir <strong>kainynai</strong> — saugomi
              tik jūsų paskyroje, neperduodami kitiems vartotojams.</li>
          </ul>

          <h3>2.3 Naudojimo statistika</h3>
          <ul>
            <li><strong>Veiksmų žurnalas</strong> — kada įkėlėte projektą, kiek kambarių, kokia trukmė AI analizė.</li>
            <li><strong>Korekcijų žurnalas</strong> — kai pakeičiate AI rezultatus (pvz. „drabužinės nedažomos"),
              saugome lauko pavadinimą, senąją ir naująją reikšmę. Naudojama AI promptų tobulinimui.
              Niekuomet neperduodama tretiesiems asmenims, niekuomet nesusiejama su jūsų tapatybe
              po anonimizacijos.</li>
            <li><strong>API kaštų sąnaudos</strong> — kiek mūsų sąskaita kainavo jūsų ekstrakcija
              (Anthropic Vision tokens). Naudojama dienos limitams ir paslaugos kainodarai.</li>
          </ul>

          <h3>2.4 Techniniai duomenys</h3>
          <ul>
            <li><strong>IP adresas</strong> — laikinai (90 dienų) saugomas serverio žurnaluose
              saugumo tikslu (rate limit, brute-force apsauga).</li>
            <li><strong>Sesijos slapukas</strong> — vienas HTTPOnly slapukas (pavadinimas
              <code>samatu_session</code>), saugantis tik vartotojo ID. Neturi jokios
              kitos informacijos, neperduoda jūsų duomenų jokiems trečiosioms šalims,
              nėra naudojamas reklamai ar sekimui.</li>
            <li><strong>Browser fingerprint duomenų NESEKAME.</strong> Nenaudojame Google Analytics,
              Facebook Pixel ar panašių sekimo įrankių.</li>
          </ul>

          <h2>3. Teisinis pagrindas (BDAR Art. 6)</h2>
          <ul>
            <li><strong>Sutartis (Art. 6 §1 b)</strong> — pagrindas paskyros duomenims, projektų saugojimui,
              AI ekstrakcijos paslaugai. Be jų negalime suteikti paslaugos.</li>
            <li><strong>Teisėtas interesas (Art. 6 §1 f)</strong> — naudojimo statistikai, korekcijų žurnalui,
              saugumo žurnalams. Mūsų interesas — gerinti paslaugą ir apsaugoti ją nuo piktnaudžiavimo.
              Galite paprieštarauti šiam tvarkymui.</li>
            <li><strong>Sutikimas (Art. 6 §1 a)</strong> — ateityje, jei pridėsime el. laiškų rinkodarą
              (dabar tokios nėra). Visada galėsite atšaukti.</li>
          </ul>

          <h2>4. Duomenų perdavimas tretiesiems asmenims</h2>
          <ul>
            <li><strong>Anthropic (JAV)</strong> — kai analizuojame jūsų PDF brėžinį, jis siunčiamas
              Anthropic Claude Vision API. Anthropic įsipareigoja:
              <ul>
                <li>Per 30 dienų ištrinti API duomenis</li>
                <li>NENAUDOTI jų modeliui treniruoti</li>
                <li>Šifruotai perduoti</li>
              </ul>
              Žr. <a href="https://www.anthropic.com/legal/privacy" target="_blank" rel="noopener">anthropic.com/legal/privacy</a>.
              Perdavimas už ES ribų vykdomas pagal Standartines sutartines sąlygas (SCC).
            </li>
            <li><strong>Google (JAV)</strong> — jei pasirenkate Google prisijungimą, OAuth flow'as
              perduoda jūsų autentifikaciją Google. Mes negauname jūsų Google slaptažodžio,
              tik tapatybės patvirtinimą + el. paštą + vardą.</li>
            <li><strong>Hostingo paslaugų teikėjas</strong> — serveriai veikia ES (Pathon
              infrastruktūra arba ES regiono debesų paslauga). Konkretų teikėją galima
              sužinoti paklausus.</li>
            <li><strong>Niekam kitam</strong> — neparduodame, neperduodame jūsų duomenų rinkodaros,
              draudimo ar kitomis tikslais. Jokio jūsų duomenų pardavimo NĖRA ir NEBUS.</li>
          </ul>

          <h2>5. Kiek laiko saugome</h2>
          <ul>
            <li><strong>Aktyvi paskyra</strong> — kol egzistuoja paskyra.</li>
            <li><strong>Ištrinta paskyra</strong> — 30 dienų soft-delete (atsarginei
              kopijai jūsų duomenims atstatyti, jei suklydote), po to visiškas ištrynimas
              iš duomenų bazės ir atsarginių kopijų.</li>
            <li><strong>Projektų PDF</strong> — kol egzistuoja projektas. Galite ištrinti projektą bet kuriuo metu.</li>
            <li><strong>Korekcijų žurnalas</strong> — anonimizuotas (be vartotojo ID),
              saugomas neribotai statistinei analizei.</li>
            <li><strong>Serverio žurnalai (su IP)</strong> — 90 dienų, tada automatiškai šalinami.</li>
            <li><strong>Apmokestinimo įrašai</strong> — 10 metų pagal LT mokesčių įstatymus
              (kai pradėsime taikyti mokestį už paslaugą).</li>
          </ul>

          <h2>6. Jūsų teisės (BDAR)</h2>
          <p>Pagal BDAR jūs turite šias teises:</p>
          <ul>
            <li><strong>Susipažinti</strong> (Art. 15) — sužinoti, kokius duomenis apie jus turime.
              Pateikiame per 30 dienų nuo prašymo gavimo.</li>
            <li><strong>Ištaisyti</strong> (Art. 16) — taisyti netikslumus jūsų paskyroje.</li>
            <li><strong>Ištrinti</strong> (Art. 17, „teisė būti pamirštam") — pašalinti duomenis.
              Galite tai padaryti savarankiškai per nustatymus arba paprašyti
              <a href="mailto:solutions@pathon.eu">solutions@pathon.eu</a>.</li>
            <li><strong>Apriboti tvarkymą</strong> (Art. 18).</li>
            <li><strong>Perkelti duomenis</strong> (Art. 20) — gauti savo projektus
              struktūruotu formatu (Excel/PDF/JSON eksporto).</li>
            <li><strong>Paprieštarauti</strong> (Art. 21) — teisėto intereso pagrindu vykdomam tvarkymui.</li>
            <li><strong>Atšaukti sutikimą</strong> — bet kuriuo metu, jei pradėjote duoti.</li>
            <li><strong>Pateikti skundą</strong> — Valstybinei duomenų apsaugos inspekcijai:
              <a href="https://vdai.lrv.lt" target="_blank" rel="noopener">vdai.lrv.lt</a>,
              tel. (8&nbsp;5)&nbsp;271&nbsp;2804.</li>
          </ul>

          <h2>7. Saugumas</h2>
          <ul>
            <li>Slaptažodžiai saugomi bcrypt maišomuoju (work factor 12).</li>
            <li>Visi duomenys perduodami HTTPS šifruotai.</li>
            <li>Sesijos slapukas yra HTTPOnly, SameSite=Lax, pasirašytas serverio raktu.</li>
            <li>Duomenų bazėje šifruojami slapti duomenys (slaptažodžiai, OAuth refresh tokens).</li>
            <li>Reguliariai atnaujinamos priklausomybės ir saugumo pataisos.</li>
            <li>Naudotojų ID logose anonimizuojami.</li>
          </ul>
          <p>
            Tačiau jokia internetinė sistema NĖRA 100% saugi. Naudokite tvirtus slaptažodžius,
            nedalinkitės jais, įjunkite naršyklės atnaujinimus.
          </p>

          <h2>8. Duomenų pažeidimo pranešimas</h2>
          <p>
            Jei įvyks duomenų pažeidimas, kuriame yra rizika jūsų teisėms ir laisvėms,
            <strong>per 72 valandas</strong> nuo pažeidimo aptikimo:
          </p>
          <ul>
            <li>Pranešime Valstybinei duomenų apsaugos inspekcijai (BDAR Art. 33).</li>
            <li>Pranešime jums el. paštu, jei pažeidimas susijęs su jūsų asmens duomenimis (Art. 34).</li>
          </ul>

          <h2>9. Slapukai</h2>
          <p>
            Naudojame VIENĄ slapuką: <code>samatu_session</code> — prisijungimo būsenai
            išlaikyti. Šis slapukas yra „esminis" pagal LT Elektroninių ryšių įstatymą
            (29¹ str.) — jam atskiras sutikimas nereikalingas, nes be jo paslauga
            nefunkcionuotų. Reklamos, analitikos, sekimo slapukų NĖRA.
          </p>

          <h2>10. Vaikų duomenys</h2>
          <p>
            Mūsų paslauga skirta verslo vartotojams. Sąmoningai nerinkame asmens duomenų
            iš vaikų iki 16 metų. Jei sužinosime, kad netyčia surinkome tokius duomenis,
            juos nedelsdami pašalinsime.
          </p>

          <h2>11. Šios politikos pakeitimai</h2>
          <p>
            Atnaujinę šią politiką, pranešime jums el. paštu ir per paslaugą. Esminiai
            pakeitimai įsigalios praėjus <strong>30 dienų</strong> nuo pranešimo. Smulkūs
            pakeitimai (pvz. typo korekcijos) gali įsigalioti iškart.
          </p>
          <p>
            Šios politikos versijų istorija saugoma viešai
            <a href="/terms"> Naudojimo sąlygų</a> puslapyje.
          </p>

          <h2>12. Kontaktai</h2>
          <p>
            Klausimai dėl privatumo, prašymai dėl duomenų:
            <a href="mailto:solutions@pathon.eu">solutions@pathon.eu</a>.
            Atsakome per 30 dienų.
          </p>

          <p className="text-sm text-muted-foreground mt-8">
            Ši politika parengta pagal BDAR (2016/679), LR Asmens duomenų teisinės
            apsaugos įstatymą ir LR Elektroninių ryšių įstatymą. Neapima visų galimų
            scenarijų — jei kas neaišku, susisiekite su mumis.
          </p>
        </article>
      </div>
    </div>
  );
}
