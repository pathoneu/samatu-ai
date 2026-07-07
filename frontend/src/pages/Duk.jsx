/**
 * DUK — dažniausiai užduodami klausimai (public, SEO/GEO page).
 *
 * Marketing role (2026-07-06): question-phrased content is what AI answer
 * engines (ChatGPT/Perplexity/AI Overviews) cite, and what long-tail Google
 * queries match. Every answer is HONEST per house rules — accuracy limits and
 * the "patikrinkite prieš pasiūlymą" duty are stated, not hidden.
 *
 * The QA list below is the single source of truth: it renders the visible
 * page AND the FAQPage JSON-LD (setJsonLd) — the two can never drift apart.
 */
import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import LegalLayout, { Section, P } from '@/components/legal/LegalLayout';
import { setJsonLd } from '@/lib/seo';

const QA = [
  {
    q: 'Kas yra Pathon ir kaip jis veikia?',
    a: 'Pathon — statybų kiekių ir sąmatų skaičiavimo platforma. Įkeliate statybos projekto PDF brėžinį; sistema atpažįsta patalpas ir elementus (sienas, duris, langus, plyteles, LED nišas), apskaičiuoja kiekius pagal Lietuvos sąmatininkų praktiką ir parengia kiekių žiniaraštį bei sąmatą. Jūs peržiūrite pažymėtas vietas ir suvedate savo įkainius.',
  },
  {
    q: 'Kiek laiko užtrunka paruošti sąmatą?',
    a: 'Brėžinio nuskaitymas paprastai trunka 10–15 minučių (priklauso nuo lapų skaičiaus). Po to kiekiai jau paskaičiuoti — lieka peržiūrėti pažymėtas vietas ir suvesti kainas. Palyginimui: rankinis kiekių skaičiavimas užtrunka nuo kelių valandų iki kelių dienų arba kainuoja €200–500 perkant iš sąmatininko.',
  },
  {
    q: 'Ar galiu pasitikėti automatiškai apskaičiuotais kiekiais?',
    a: 'Kiekvienas kiekis turi pasitikėjimo indikatorių: žalias — nuskaityta tiesiai iš brėžinio, geltonas — apskaičiuota su prielaidomis, raudonas — naudota numatytoji reikšmė. Skaičiavimo formulės atitinka profesionalių sąmatininkų praktiką (~1 % tikslumu, kai pradiniai duomenys teisingi), tačiau simbolių atpažinimas iš brėžinių nėra tobulas — todėl sistema aiškiai parodo, ką patikrinti pirmiausia. Prieš naudodami kiekius komerciniame pasiūlyme, juos peržiūrėkite.',
  },
  {
    q: 'Kokius brėžinius Pathon skaito?',
    a: 'Geriausiai — interjero / vidaus apdailos projektus PDF formatu: aukštų planus, sienų išklotines, lubų ir grindų planus, eksplikacijas. Taip pat nuskaitomi kiekių žiniaraščiai iš kitų statybos dalių (konstrukcijos, elektra, santechnika). Tinka tiek vektoriniai, tiek skenuoti (rastriniai) PDF.',
  },
  {
    q: 'Kiek kainuoja Pathon?',
    a: 'Vienkartinis projektas — €12. „Pro" planas — €49/mėn. (10 projektų per mėnesį), „Studio" — €149/mėn. (35 projektai). Naujoms įmonėms — vienas nemokamas bandomasis projektas. Į kainą įskaičiuotas visas nuskaitymas, perskaičiavimai ir eksportai; kainos nurodytos be PVM.',
  },
  {
    q: 'Ar Pathon pakeičia sąmatininką?',
    a: 'Pathon atlieka techninę kiekių skaičiavimo dalį — tą, kuri užima daugiausiai laiko. Sprendimus (įkainius, technologijas, pasiūlymo strategiją) priimate jūs. Mažoms įmonėms tai dažnai reiškia, kad savininkas sąmatą pasidaro pats per vakarą, o ne laukia savaitę ir moka už paslaugą.',
  },
  {
    q: 'Į kokius formatus galima eksportuoti?',
    a: 'Excel (su gyvomis formulėmis — keičiant kiekius ar kainas, sumos persiskaičiuoja pačiame faile) ir PDF (LOKALINĖS SĄMATOS formatas su skyrių sumomis, PVM eilute ir parašų bloku). Kiekių žiniaraštį galima perkelti ir į kitas sąmatų programas.',
  },
  {
    q: 'Kaip skaičiuojamas PVM?',
    a: 'Standartiškai taikomas 21 % PVM. Daugiabučių renovacijos projektams palaikomas atvirkštinis apmokestinimas (reverse charge) pagal LT tvarką — PVM eilutė formuojama atitinkamai.',
  },
  {
    q: 'Ar mano brėžiniai ir duomenys saugūs?',
    a: 'Taip. Prieiga prie projektų — tik su jūsų paskyra; failai saugomi ES duomenų centruose; projektų duomenys nenaudojami viešiems AI modeliams apmokyti. Detaliau — privatumo politikoje.',
  },
  {
    q: 'Ką daryti, jei sistema kažką atpažino ne taip?',
    a: 'Pataisyti galima tiesiai programoje: pakeisti patalpos duomenis, kiekius ar prielaidas (lubų aukštį, glaistymo lygį ir kt.) — visos susijusios eilutės perskaičiuojamos akimirksniu, be pakartotinio nuskaitymo. Jūsų suvestos kainos išlieka.',
  },
];

export default function Duk() {
  // <title>/description/canonical come from LegalLayout (title + intro props);
  // this effect only owns the FAQPage structured data.
  useEffect(() => {
    setJsonLd('jsonld-faq', {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: QA.map(({ q, a }) => ({
        '@type': 'Question',
        name: q,
        acceptedAnswer: { '@type': 'Answer', text: a },
      })),
    });
    return () => document.getElementById('jsonld-faq')?.remove();
  }, []);

  return (
    <LegalLayout
      eyebrow="Pagalba"
      index="DUK-01"
      title="Dažniausiai užduodami klausimai"
      intro="Trumpai ir be pagražinimų: kaip Pathon skaičiuoja kiekius iš PDF brėžinių, kiek tai kainuoja, kaip veikia eksportas į Excel bei PDF ir kur yra sistemos ribos."
      updated="2026-07-06"
      effective="2026-07-06"
    >
      {QA.map((item, i) => (
        <Section key={item.q} n={i + 1} title={item.q}>
          <P>{item.a}</P>
        </Section>
      ))}
      <Section n={QA.length + 1} title="Neradote atsakymo?">
        <P>
          Parašykite mums el. paštu{' '}
          <a href="mailto:solutions@pathon.eu" className="text-primary hover:underline">
            solutions@pathon.eu
          </a>{' '}
          arba išbandykite patys —{' '}
          <Link to="/register" className="text-primary hover:underline">
            pirmasis projektas įmonei nemokamas
          </Link>.
        </P>
      </Section>
    </LegalLayout>
  );
}
