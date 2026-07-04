/**
 * Privatumo politika — Pathon (LT, BDAR/GDPR pagrįsta).
 *
 * 2026-07-05: perrašyta į naują DARK graphite identitetą (LegalLayout),
 * išplėsta pagal B2B / statybų SaaS scenarijų. TEISINIS STATUSAS: šis tekstas
 * yra PROFESIONALUS PROJEKTAS, o ne teisinė konsultacija. Prieš publikavimą
 * jį turi peržiūrėti teisininkas. Palikti [...] žymekliai — įmonės rekvizitai
 * (kodas, adresas), kuriuos užpildo įkūrėjas.
 */
import React from 'react';
import LegalLayout, {
  Section, SubHead, P, Term, UL, LI, Callout, Todo,
} from '@/components/legal/LegalLayout';
import { Link } from 'react-router-dom';

export default function Privacy() {
  return (
    <LegalLayout
      eyebrow="Teisė / Privatumas"
      index="LEX-01"
      title="Privatumo politika"
      intro="Kaip Pathon renka, naudoja, saugo ir apsaugo jūsų asmens duomenis pagal Bendrąjį duomenų apsaugos reglamentą (BDAR) ir Lietuvos Respublikos teisės aktus."
      updated="2026-07-05"
      effective="2026-07-05"
    >
      <Section n={1} title="Duomenų valdytojas">
        <P>
          Šią paslaugą teikia <Term>Pathon, MB</Term> (toliau — „Pathon", „mes"
          arba „mūsų") — duomenų valdytojas pagal BDAR (Reglamentas (ES)
          2016/679).
        </P>
        <UL>
          <LI>Įmonės kodas: <Todo>[įmonės kodas]</Todo></LI>
          <LI>Registracijos adresas: <Todo>[adresas]</Todo></LI>
          <LI>
            Kontaktai duomenų klausimais:{' '}
            <a href="mailto:solutions@pathon.eu" className="text-primary hover:underline">solutions@pathon.eu</a>
          </LI>
        </UL>
        <P>
          Ši politika taikoma naudojantis Pathon interneto svetaine ir
          paslaugomis. Ji paaiškina, kokius asmens duomenis tvarkome, kokiais
          tikslais, kokiu teisiniu pagrindu ir kokias teises turite.
        </P>
      </Section>

      <Section n={2} title="Kokius duomenis tvarkome">
        <SubHead>2.1 Paskyros duomenys</SubHead>
        <UL>
          <LI><Term>El. paštas</Term> — tapatybei nustatyti, prisijungti ir techninei komunikacijai.</LI>
          <LI><Term>Vardas / pavardė</Term> — paskyrai ir eksportuojamiems dokumentams personalizuoti.</LI>
          <LI><Term>Įmonės pavadinimas, įmonės kodas, PVM mokėtojo kodas</Term> — sąskaitoms faktūroms ir dokumentų rekvizitams.</LI>
          <LI>
            <Term>Slaptažodis</Term> — saugomas tik vienakrypčiu bcrypt maišos algoritmu.
            Atviro teksto slaptažodžio nesaugome ir nematome. Jei prisijungiate per
            Google, saugome tik Google paskyros identifikatorių, el. paštą ir vardą.
          </LI>
        </UL>

        <SubHead>2.2 Turinio (projektų) duomenys</SubHead>
        <UL>
          <LI>
            <Term>Įkelti brėžiniai ir PDF failai</Term> — susiejami tik su jūsų paskyra.
            Šie failai apdorojami dirbtinio intelekto (AI) priemonėmis, kad būtų
            ištraukti kiekiai (žr. 4 skyrių).
          </LI>
          <LI><Term>Ištraukti kiekiai ir sąmatos</Term> — patalpos, plotai, ilgiai, tūriai, pozicijos.</LI>
          <LI><Term>Įvestos kainos ir kainynai</Term> — saugomi tik jūsų paskyroje, neperduodami kitiems naudotojams.</LI>
        </UL>

        <SubHead>2.3 Techniniai duomenys</SubHead>
        <UL>
          <LI><Term>IP adresas</Term> — laikinai saugomas serverio žurnaluose saugumo tikslais (rate limit, apsauga nuo piktnaudžiavimo).</LI>
          <LI><Term>Įrenginio ir naršyklės duomenys</Term> — naršyklės tipas, operacinė sistema, kalba — paslaugos suderinamumui ir saugumui užtikrinti.</LI>
          <LI>
            <Term>Slapukai</Term> — būtinasis sesijos slapukas ir, tik su jūsų sutikimu,
            analitiniai bei rinkodaros slapukai. Išsamiau —{' '}
            <Link to="/cookies" className="text-primary hover:underline">Slapukų politikoje</Link>.
          </LI>
        </UL>

        <SubHead>2.4 Mokėjimų duomenys</SubHead>
        <P>
          Mokėjimus tvarko <Term>Stripe</Term>. Kortelės numerio, galiojimo ar CVV
          <em> Pathon nemato ir nesaugo</em> — šiuos duomenis tiesiogiai tvarko Stripe
          kaip savarankiškas duomenų valdytojas. Mes gauname tik mokėjimo būseną,
          sumą, datą ir dalinius sąskaitos rekvizitus, reikalingus apskaitai.
        </P>
      </Section>

      <Section n={3} title="Tikslai ir teisinis pagrindas">
        <P>
          Kiekvieną duomenų tvarkymo veiklą pagrindžia bent vienas BDAR 6
          straipsnio teisinis pagrindas:
        </P>
        <UL>
          <LI>
            <Term>Paslaugos teikimas</Term> (paskyra, projektų saugojimas, AI ekstrakcija) —
            <em> sutarties vykdymas</em> (BDAR 6 str. 1 d. b p.). Be šių duomenų paslauga negalima.
          </LI>
          <LI>
            <Term>Sąskaitos ir apskaita</Term> —
            <em> teisinės prievolės vykdymas</em> (6 str. 1 d. c p.), pagal LR buhalterinės
            apskaitos ir mokesčių teisės aktus.
          </LI>
          <LI>
            <Term>Saugumas ir paslaugos tobulinimas</Term> (žurnalai, apsauga nuo piktnaudžiavimo,
            kokybės gerinimas) — <em>teisėtas interesas</em> (6 str. 1 d. f p.). Šiam tvarkymui galite paprieštarauti.
          </LI>
          <LI>
            <Term>Rinkodara ir analitika</Term> (naujienlaiškiai, analitiniai/rinkodaros slapukai) —
            <em> jūsų sutikimas</em> (6 str. 1 d. a p.). Sutikimą galite bet kada atšaukti.
          </LI>
        </UL>
      </Section>

      <Section n={4} title="Duomenų tvarkytojai ir perdavimas">
        <P>
          Pasitelkiame patikimus paslaugų teikėjus (duomenų tvarkytojus), su
          kuriais sudaryta duomenų tvarkymo sutartis. Jie tvarko duomenis tik pagal
          mūsų nurodymus.
        </P>
        <Callout title="Svarbu — AI apdorojimas">
          <P>
            Įkelti brėžiniai apdorojami dirbtinio intelekto priemonėmis. Analizei
            failo turinys perduodamas <Term>Anthropic</Term> (Claude) API. Tai reiškia,
            kad brėžinio vaizdas laikinai išsiunčiamas AI paslaugų teikėjui, kad būtų
            atpažintos patalpos ir apskaičiuoti kiekiai.
          </P>
        </Callout>
        <UL>
          <LI>
            <Term>Anthropic (Claude), JAV</Term> — brėžinių AI apdorojimas. Perdavimas už
            ES/EEE ribų vykdomas remiantis Europos Komisijos Standartinėmis
            sutartinėmis sąlygomis (SCC). Anthropic įsipareigoja nenaudoti API duomenų
            modeliams treniruoti. Žr.{' '}
            <a href="https://www.anthropic.com/legal/privacy" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">anthropic.com/legal/privacy</a>.
          </LI>
          <LI>
            <Term>Stripe</Term> — mokėjimų tvarkymas. Perdavimai už ES ribų vykdomi pagal
            SCC. Žr.{' '}
            <a href="https://stripe.com/privacy" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">stripe.com/privacy</a>.
          </LI>
          <LI>
            <Term>Debesijos priegloba ir failų saugykla</Term> — serverių ir objektų saugyklos
            (angl. object storage) paslaugos, naudojamos paskyroms, projektams ir PDF
            failams saugoti. Konkretų teikėją galima sužinoti paklausus el. paštu.
          </LI>
          <LI>
            <Term>Google</Term> — jei pasirenkate prisijungimą per Google, tapatybės
            patvirtinimui naudojamas Google OAuth. Google slaptažodžio negauname.
          </LI>
        </UL>
        <P>
          Jūsų asmens duomenų <Term>neparduodame</Term> ir neperduodame tretiesiems asmenims
          rinkodaros tikslais.
        </P>
      </Section>

      <Section n={5} title="Saugojimo terminai">
        <UL>
          <LI><Term>Paskyros duomenys</Term> — kol paskyra aktyvi; ištrynus paskyrą — iki 30 dienų (atkūrimo langas), po to visiškai pašalinami.</LI>
          <LI><Term>Projektų failai ir sąmatos</Term> — kol egzistuoja projektas; galite juos ištrinti bet kada.</LI>
          <LI><Term>Brėžiniai, perduoti AI apdorojimui</Term> — pas AI paslaugų teikėją laikomi ne ilgiau, nei numatyta jo politikoje (Anthropic — įprastai iki 30 dienų).</LI>
          <LI><Term>Serverio žurnalai (su IP)</Term> — iki 90 dienų, po to automatiškai šalinami.</LI>
          <LI><Term>Apskaitos ir mokėjimų įrašai</Term> — pagal LR mokesčių ir apskaitos teisės aktus (paprastai 10 metų).</LI>
        </UL>
      </Section>

      <Section n={6} title="Jūsų teisės">
        <P>Pagal BDAR jūs turite šias teises dėl savo asmens duomenų:</P>
        <UL>
          <LI><Term>Susipažinti</Term> (15 str.) — sužinoti, kokius duomenis apie jus tvarkome.</LI>
          <LI><Term>Ištaisyti</Term> (16 str.) — pataisyti netikslius ar papildyti neišsamius duomenis.</LI>
          <LI><Term>Ištrinti</Term> (17 str., „teisė būti pamirštam") — pašalinti duomenis, kai nebėra teisinio pagrindo juos tvarkyti.</LI>
          <LI><Term>Apriboti tvarkymą</Term> (18 str.).</LI>
          <LI><Term>Perkelti duomenis</Term> (20 str.) — gauti savo projektus struktūruotu, kompiuterio skaitomu formatu (Excel / PDF / JSON eksportas).</LI>
          <LI><Term>Prieštarauti</Term> (21 str.) — teisėto intereso pagrindu vykdomam tvarkymui.</LI>
          <LI><Term>Atšaukti sutikimą</Term> — bet kada, neveikiant atgaline data (pvz. rinkodaros ar analitikos slapukams).</LI>
        </UL>
        <Callout title="Skundas priežiūros institucijai">
          <P>
            Jei manote, kad jūsų teisės pažeistos, turite teisę pateikti skundą
            priežiūros institucijai — <Term>Valstybinei duomenų apsaugos inspekcijai (VDAI)</Term>:{' '}
            <a href="https://vdai.lrv.lt" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">vdai.lrv.lt</a>.
            Vis dėlto pirmiausia kviečiame kreiptis į mus — stengsimės išspręsti klausimą tiesiogiai.
          </P>
        </Callout>
        <P>
          Norėdami pasinaudoti teisėmis, rašykite{' '}
          <a href="mailto:solutions@pathon.eu" className="text-primary hover:underline">solutions@pathon.eu</a>.
          Atsakome per 30 dienų nuo prašymo gavimo.
        </P>
      </Section>

      <Section n={7} title="Slapukai">
        <P>
          Naudojame būtinuosius slapukus paslaugai veikti, o analitinius ir
          rinkodaros slapukus — tik gavę jūsų sutikimą. Slapukų kategorijas,
          konkrečius slapukus ir sutikimo valdymą aprašo{' '}
          <Link to="/cookies" className="text-primary hover:underline">Slapukų politika</Link>.
        </P>
      </Section>

      <Section n={8} title="Duomenų saugumas">
        <UL>
          <LI>Visi duomenys perduodami šifruotu HTTPS ryšiu.</LI>
          <LI>Slaptažodžiai saugomi tik bcrypt maišos pavidalu.</LI>
          <LI>Sesijos slapukas yra HTTPOnly ir SameSite=Lax, pasirašytas serverio raktu.</LI>
          <LI>Prieiga prie duomenų ribojama; reguliariai diegiamos saugumo pataisos.</LI>
        </UL>
        <P>
          Vis dėlto jokia internetinė sistema nėra visiškai apsaugota. Įvykus asmens
          duomenų saugumo pažeidimui, kuris gali kelti riziką jūsų teisėms ir
          laisvėms, pranešime priežiūros institucijai per 72 valandas (BDAR 33 str.)
          ir, esant didelei rizikai, informuosime jus (34 str.).
        </P>
      </Section>

      <Section n={9} title="Politikos pakeitimai">
        <P>
          Šią politiką galime atnaujinti. Apie esminius pakeitimus pranešime el.
          paštu ir (arba) per paslaugą. Rekomenduojame periodiškai peržiūrėti šį
          puslapį — viršuje nurodyta paskutinio atnaujinimo data.
        </P>
      </Section>

      <Section n={10} title="Kontaktai">
        <P>
          Visais privatumo ir asmens duomenų klausimais rašykite{' '}
          <a href="mailto:solutions@pathon.eu" className="text-primary hover:underline">solutions@pathon.eu</a>.
        </P>
      </Section>
    </LegalLayout>
  );
}
