/**
 * /kiekiai-is-brezinio — BoFu landing page (docs/marketing/seo-playbook.md §3.2).
 * Outcome page mirroring the hero: PDF brėžinys → kiekių žiniaraštis → sąmata.
 *
 * ⚠️ JUODRAŠTIS (2026-07-06): visą LT tekstą prieš publikavimą peržiūri ir
 * nušlifuoja founderis (LT copy rule: Claude drafts → founder polishes → publish).
 * Playbook mini „step-by-step su ekrano nuotraukomis“ — nuotraukų dar nėra;
 * žingsniai aprašyti tekstu, founderis vėliau gali įterpti realias ekrano
 * nuotraukas prie 1 sekcijos.
 *
 * Schema: Article.
 */
import React, { useEffect } from 'react';
import { Link } from 'react-router';
import { ArrowRight } from 'lucide-react';
import MarketingLayout from '@/components/marketing/MarketingLayout';
import {
  Section, SubHead, P, Term, UL, LI, Callout, DefTable,
} from '@/components/legal/LegalLayout';
import { setPageMeta, setJsonLd } from '@/lib/seo';

const PATH = '/kiekiai-is-brezinio';
const URL = `https://pathon.eu${PATH}`;

/** Mono chip strip: PDF → kiekiai → XLSX/PDF (the product, in one line). */
function FlowStrip() {
  const steps = ['PDF brėžinys', 'Kiekių žiniaraštis', 'Sąmata · XLSX / PDF'];
  return (
    <div className="mt-5 flex flex-wrap items-center gap-2.5" aria-hidden>
      {steps.map((label, i) => (
        <React.Fragment key={label}>
          {i > 0 && <ArrowRight className="w-4 h-4 text-primary shrink-0" />}
          <span className="font-mono text-[11.5px] tracking-[0.04em] px-3 py-1.5 rounded-lg border border-border-strong bg-surface-2 text-foreground/90">
            {label}
          </span>
        </React.Fragment>
      ))}
    </div>
  );
}

export default function KiekiaiIsBrezinio() {
  useEffect(() => {
    setPageMeta({
      title: 'Kiekiai iš PDF brėžinio per valandą',
      description:
        'Įkelkite statybos projekto PDF — Pathon atpažįsta patalpas, apskaičiuoja kiekius ir parengia kiekių žiniaraštį su sąmata. Eksportas į Excel ir PDF.',
      path: PATH,
    });
    setJsonLd('jsonld-article-kiekiai', {
      '@context': 'https://schema.org',
      '@type': 'Article',
      '@id': `${URL}#article`,
      headline: 'Kiekiai iš PDF brėžinio per valandą',
      description:
        'Kaip iš statybos projekto PDF brėžinio automatiškai apskaičiuojami kiekiai: žingsniai, ką sistema išmatuoja, kaip tikrinti kiekius ir eksportas į Excel bei PDF.',
      inLanguage: 'lt',
      mainEntityOfPage: URL,
      image: 'https://pathon.eu/og-image.png',
      datePublished: '2026-07-06',
      dateModified: '2026-07-06',
      author: { '@id': 'https://pathon.eu/#org' },
      publisher: { '@id': 'https://pathon.eu/#org' },
    });
    return () => document.getElementById('jsonld-article-kiekiai')?.remove();
  }, []);

  return (
    <MarketingLayout
      eyebrow="Gidas / Kiekiai"
      index="GID-02"
      title="Kiekiai iš PDF brėžinio per valandą"
      intro="Kaip iš statybos projekto PDF gimsta kiekių žiniaraštis ir sąmata: žingsniai, ką sistema išmatuoja ir kur — sąžiningai — jos ribos."
      updated="2026-07-06"
      related={[
        { to: '/samatininko-kaina', label: 'Kiek laiko atima sąmata' },
        { to: '/vidaus-apdailos-samata', label: 'Vidaus apdailos sąmata' },
        { to: '/duk', label: 'DUK' },
      ]}
    >
      <Section n={1} title="Kaip tai veikia: trys žingsniai">
        <FlowStrip />
        <SubHead>1. Įkeliate projekto PDF</SubHead>
        <P>
          Tinka aukštų planai, sienų išklotinės, lubų ir grindų planai,
          eksplikacijos — geriausiai vektoriniai PDF; skenuotuose perskaitoma
          mažiau, todėl juos reikia tikrinti atidžiau. Jokio paruošimo: keliate
          tą patį PDF, kurį gavote iš projektuotojo.
        </P>
        <SubHead>2. Sistema nuskaito ir apskaičiuoja</SubHead>
        <P>
          <Link to="/about" className="text-primary hover:underline">Pathon</Link>{' '}
          klasifikuoja kiekvieną lapą (planas, išklotinė, lubų planas…),
          atpažįsta patalpas ir elementus, tada pritaiko Lietuvos sąmatininkų
          praktikos formules: plotai, perimetrai, angų atėmimai, atliekų
          koeficientai. Nuskaitymas paprastai trunka 15–35 minutes —
          trukmė priklauso nuo lapų skaičiaus; langą galite uždaryti ir
          grįžti vėliau.
        </P>
        <SubHead>3. Peržiūrite ir suvedate kainas</SubHead>
        <P>
          Programa užduoda kelis klausimus apie projektą, o prie kiekvienos
          reikšmės rodo vietą brėžinyje, iš kurios ji atėjo. Pakoreguojate prielaidas (lubų aukštį,
          glaistymo lygį, angas), suvedate savo įkainius — sumos
          persiskaičiuoja akimirksniu. Tuomet eksportuojate į Excel arba PDF.
        </P>
      </Section>

      <Section n={2} title="Ką sistema išmatuoja">
        <UL>
          <LI>
            <Term>Dažomus plotus</Term> — sienos ir lubos atskiromis eilutėmis,
            su angų atėmimu ir angokraščiais.
          </LI>
          <LI>
            <Term>Grindis ir grindjuostes</Term> — dangos plotai pagal patalpas,
            grindjuosčių ilgiai be durų angų.
          </LI>
          <LI>
            <Term>Plytelių zonas</Term> — iš sienų išklotinių, su aukščiais ir
            atliekų koeficientais pagal klojimo raštą.
          </LI>
          <LI>
            <Term>Glaistymą ir gruntavimą</Term> — kaip atskiras eilutes, pagal
            pasirinktą kokybės lygį (Q2–Q4).
          </LI>
          <LI>
            <Term>Medžiagų kiekius</Term> — dažų litrus, glaisto kilogramus,
            gipso kartono lapus su atliekomis.
          </LI>
          <LI>
            <Term>Lubų elementus</Term> — perimetrus, LED nišų ilgius, užuolaidų
            nišas iš lubų planų.
          </LI>
          <LI>
            <Term>Elektros ir santechnikos taškus</Term> — rozetes, jungiklius,
            šviestuvus, prietaisus iš atitinkamų planų.
          </LI>
        </UL>
        <P>
          Kokios formulės slypi po šiais kiekiais — detaliai aprašėme puslapyje{' '}
          <Link to="/vidaus-apdailos-samata" className="text-primary hover:underline">
            vidaus apdailos sąmata
          </Link>.
        </P>
      </Section>

      <Section n={3} title="Kokie brėžiniai tinka">
        <P>
          Giliausiai Pathon skaito <Term>interjero / vidaus apdailos
          projektus</Term>: planus, išklotines, lubų planus, eksplikacijas. Iš
          kitų statybos dalių (konstrukcijos, elektra, santechnika) nuskaitomi
          kiekių žiniaraščiai — jų eilutės perkeliamos į sąmatą su vienetais ir
          kiekiais.
        </P>
        <P>
          Sąžiningas pastebėjimas: kuo išsamesnis projektas, tuo daugiau
          perskaitoma tiesiai iš brėžinio. Jei išklotinių ar eksplikacijų nėra, sistema skaičiuoja
          su prielaidomis ir aiškiai jas parodo — tokias vietas verta peržiūrėti
          pirmiausia.
        </P>
      </Section>

      <Section n={4} title="Kaip tikrinate kiekius">
        <P>
          Joks įrankis (nei žmogus) neatpažįsta brėžinių šimtu procentų. Užuot
          apsimetę, jog klaidų nebūna, prie kiekvieno kiekio rodome vietą
          brėžinyje, iš kurios jis paimtas, o ko nustatyti nepavyko — klausiame
          jūsų. Eilutėse taip pat matote, kaip kiekis gautas:
        </P>
        <UL>
          <LI>
            <Term>Žalias</Term> — reikšmė nuskaityta tiesiai iš brėžinio
            (matmuo, eksplikacijos lentelė, užrašas).
          </LI>
          <LI>
            <Term>Geltonas</Term> — apskaičiuota iš dalinių duomenų su
            prielaidomis (pvz., standartinis lango dydis).
          </LI>
          <LI>
            <Term>Raudonas</Term> — panaudota numatytoji reikšmė, nes brėžinyje
            informacijos nepakako. Tikrinti būtina.
          </LI>
        </UL>
        <P>
          Papildomai veikia patikros taisyklės — pavyzdžiui, dažomas sienų
          plotas paprastai būna 2,5–4 kartus didesnis už grindų plotą. Jei
          santykis įtartinas, sistema įspėja, o ne nutyli.
        </P>
      </Section>

      <Section n={5} title="Klaidos, kurias rankinis skaičiavimas daro dažniausiai">
        <P>
          Šias klaidas matome nuolat — jos ne dėl kvalifikacijos stokos, o dėl
          to, kad žmogus, tris valandas matuojantis PDF, pavargsta:
        </P>
        <UL>
          <LI>
            <Term>Nepatikrintas mastelis.</Term> Brėžinys atspausdintas ar
            eksportuotas kitu masteliu, nei parašyta — ir visi ilgiai „nuplaukia“
            10–20 %. Mastelį būtina pasitikrinti pagal žinomą matmenį.
          </LI>
          <LI>
            <Term>Dvigubai suskaičiuotos pertvaros</Term> — ta pati siena
            įtraukta iš abiejų gretimų patalpų pusių du kartus.
          </LI>
          <LI>
            <Term>Vienas lubų aukštis visam butui</Term>, nors koridoriuje
            pakabinamos lubos, o svetainėje — 3 m.
          </LI>
          <LI>
            <Term>Pamirštos paruošimo eilutės</Term> — gruntas ir glaistymas
            „paskendę“ dažymo įkainyje, todėl vėliau nėra kuo pagrįsti kainos.
          </LI>
          <LI>
            <Term>Praleista hidroizoliacija</Term> šlapiose zonose — viena
            dažniausiai pamirštamų eilučių apdailos sąmatose.
          </LI>
          <LI>
            <Term>Be atliekų koeficientų</Term> — plytelės eglute be +10–15 %
            atsargos reiškia antrą užsakymą ir prastovą objekte.
          </LI>
        </UL>
        <P>
          Automatika šių klaidų nedaro dėl paties veikimo principo: formulės tos pačios visiems
          projektams, patikros taisyklės — visada įjungtos.
        </P>
      </Section>

      <Section n={6} title="Nuo kiekių iki sąmatos">
        <P>
          Kiekiai — tik pusė darbo. Suvedus įkainius, Pathon suformuoja sąmatą
          Lietuvos formatu: skyrių sumos, 21 % PVM (daugiabučių renovacijai —
          atvirkštinis apmokestinimas), medžiagų ir darbų eilutės. Eksportas:
        </P>
        <UL>
          <LI>
            <Term>Excel</Term> — su gyvomis formulėmis: pakeitus kiekį ar kainą
            faile, sumos persiskaičiuoja pačios.
          </LI>
          <LI>
            <Term>PDF</Term> — lietuviškos sąmatos formatas su skyrių sumomis, PVM
            eilute ir parašų bloku.
          </LI>
        </UL>
        <P>
          Svarbi detalė — <Term>prielaidų skydelis</Term>. Sienos storis,
          glaistymo Q lygis, langų ir durų skaičius kambaryje: visos prielaidos
          matomos ir keičiamos, o pakeitus bet kurią, susiję kiekiai
          persiskaičiuoja iš karto. Projektas pasikeitė? Ne skaičiuojate iš
          naujo, o pakoreguojate prielaidą.
        </P>
      </Section>

      <Section n={7} title="Palyginimas su rankiniu skaičiavimu">
        <DefTable
          head={['Kriterijus', 'Ranka (PDF + Excel)', 'Su Pathon']}
          rows={[
            ['Laikas kiekiams', '4–12 val.', '~15 min. + peržiūra'],
            ['Klaidų rizika', 'praleistos angos, dvigubos sienos', 'indikatoriai + patikros taisyklės'],
            ['Projekto pakeitimai', 'skaičiuoti iš naujo', 'perskaičiavimas akimirksniu'],
            ['Kaina', 'jūsų valandos', 'nuo 12 € už projektą'],
          ]}
        />
        <Callout title="Kada tai neapsimoka">
          <P>
            Jei per metus darote vieną sąmatą — greičiausiai užteks ir Excel.
            Pathon apsimoka, kai pasiūlymai kartojasi ir kiekviena laukimo
            diena kainuoja užsakymus. Kiek laiko atima kiekvienas būdas —
            palyginome puslapyje{' '}
            <Link to="/samatininko-kaina" className="text-primary hover:underline">
              kiek laiko atima sąmata
            </Link>.
          </P>
        </Callout>
      </Section>
    </MarketingLayout>
  );
}
