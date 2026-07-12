/**
 * /apva-renovacijos-kiekiai — BoFu landing page (docs/marketing/seo-playbook.md §3.4).
 * Segment page: daugiabučių modernizavimo (APVA) kiekių žiniaraštis —
 * atvirkštinis PVM, investicijų plano formatas, ETICS/stogo komponentų normos.
 *
 * ⚠️ JUODRAŠTIS (2026-07-06): visą LT tekstą prieš publikavimą peržiūri ir
 * nušlifuoja founderis (LT copy rule: Claude drafts → founder polishes → publish).
 * Ypač patikrinti: (1) atvirkštinio PVM formuluotę (teisinė precizika),
 * (2) APVA/BETA tvarkos detales — paramos sąlygos keičiasi, todėl tekste jos
 * sąmoningai paliktos bendros, (3) ar fasado/stogo galimybių aprašymas atitinka
 * dabartinį produkto stovį (interior — giliausia dalis; fasadas/stogas — pagal
 * matmenis + prielaidas).
 *
 * Schema: Article.
 */
import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import MarketingLayout from '@/components/marketing/MarketingLayout';
import {
  Section, P, Term, UL, LI, Callout, Code, DefTable,
} from '@/components/legal/LegalLayout';
import { setPageMeta, setJsonLd } from '@/lib/seo';

const PATH = '/apva-renovacijos-kiekiai';
const URL = `https://pathon.eu${PATH}`;

export default function ApvaRenovacijosKiekiai() {
  useEffect(() => {
    setPageMeta({
      title: 'APVA renovacijos kiekių žiniaraštis per dieną',
      description:
        'Daugiabučio renovacijos kiekių žiniaraštis: ETICS fasado komponentų normos, stogo kiekiai su nuolydžio koeficientais, atvirkštinis PVM ir investicijų planas.',
      path: PATH,
    });
    setJsonLd('jsonld-article-apva', {
      '@context': 'https://schema.org',
      '@type': 'Article',
      '@id': `${URL}#article`,
      headline: 'APVA renovacijos kiekių žiniaraštis — per dieną, ne per savaitę',
      description:
        'Ką apima daugiabučio modernizavimo kiekių žiniaraštis: ETICS fasado komponentai, stogo kiekiai, atvirkštinis PVM ir investicijų plano formatas.',
      inLanguage: 'lt',
      mainEntityOfPage: URL,
      image: 'https://pathon.eu/og-image.png',
      datePublished: '2026-07-06',
      dateModified: '2026-07-06',
      author: { '@id': 'https://pathon.eu/#org' },
      publisher: { '@id': 'https://pathon.eu/#org' },
    });
    return () => document.getElementById('jsonld-article-apva')?.remove();
  }, []);

  return (
    <MarketingLayout
      eyebrow="Gidas / Renovacija"
      index="GID-04"
      title="APVA renovacijos kiekių žiniaraštis — per dieną, ne per savaitę"
      intro="Daugiabučio modernizavimo pasiūlymui reikia kiekių iš visų dalių: fasado, stogo, cokolio, laiptinių. Štai iš ko tas žiniaraštis susideda — ir kaip jį paruošti greitai."
      updated="2026-07-06"
      related={[
        { to: '/vidaus-apdailos-samata', label: 'Vidaus apdailos sąmata' },
        { to: '/kiekiai-is-brezinio', label: 'Kiekiai iš PDF brėžinio' },
        { to: '/duk', label: 'DUK' },
      ]}
    >
      <Section n={1} title="Kas įeina į renovacijos kiekių žiniaraštį">
        <P>
          Daugiabučio modernizavimo projektas sujungia kelias statybos dalis į
          vieną žiniaraštį — ir būtent dėl to jo kiekiai atima tiek laiko:
        </P>
        <UL>
          <LI>
            <Term>Fasado šiltinimas (ETICS)</Term> — didžiausia apimtis:
            termoizoliacija, armavimas, tinkas, profiliai, palangės.
          </LI>
          <LI>
            <Term>Stogo šiltinimas ir danga</Term> — su parapetais, latakais,
            lietvamzdžiais.
          </LI>
          <LI>
            <Term>Cokolis ir rūsio perdanga</Term> — atskiros sistemos ir
            atskiros eilutės.
          </LI>
          <LI>
            <Term>Langų keitimas ir balkonų stiklinimas</Term> — kiekiai iš
            langų žiniaraščio ir fasadų.
          </LI>
          <LI>
            <Term>Laiptinių remontas</Term> — vidaus apdailos dalis: glaistymas,
            dažymas, grindys.
          </LI>
          <LI>
            <Term>Inžinerija</Term> — šildymo ir karšto vandens vamzdynai,
            balansavimas, izoliacija.
          </LI>
        </UL>
        <P>
          Kiekviena dalis turi savo matavimo logiką, todėl rangovui, teikiančiam
          pasiūlymą, tai reiškia kelias dienas darbo su brėžiniais — arba
          automatizuotą skaičiavimą ir dieną peržiūrai.
        </P>
      </Section>

      <Section n={2} title="ETICS fasado komponentai — normos vienam m²">
        <P>
          Fasado kiekiai skaičiuojami nuo <Term>neto ploto</Term>: bruto plotas
          (ilgis × aukštis kiekvienam fasadui) minus langai, durys ir balkonai.
          Toliau — komponentų normos šiltinamam kvadratiniam metrui:
        </P>
        <DefTable
          head={['Komponentas', 'Norma 1 m²']}
          rows={[
            ['Klijai', '5,5 kg'],
            ['Smeigės', '7 vnt.'],
            ['Armavimo tinklelis', '1,1 m² (10 % užlaida)'],
            ['Armavimo mišinys', '4,5 kg'],
            ['Gruntas', '0,25 l'],
            ['Dekoratyvinis tinkas', '3,0 kg'],
          ]}
        />
        <P>Prie jų — ilginiai elementai, kuriuos lengva pamiršti:</P>
        <UL>
          <LI><Term>Cokolinis profilis</Term> — pastato perimetras (2,5 m ilgio segmentais).</LI>
          <LI><Term>Kampų profiliai</Term> — pastato kampai + langų ir durų angokraščiai.</LI>
          <LI><Term>Palangės</Term> — langų pločiai + po 5 cm užleidimo iš abiejų pusių.</LI>
          <LI><Term>Lašikliai</Term> — langų viršaus pločiai.</LI>
        </UL>
        <P>
          Savikontrolė: smeigių turi išeiti apie 6–8 vnt./m² (jei gaunate 4 ar
          12 — klaida), o fasado neto plotas paprastai būna 15–25 % mažesnis už
          perimetro × aukščio sandaugą.
        </P>
      </Section>

      <Section n={3} title="Stogo kiekiai: nuolydžio koeficientas">
        <P>
          Dažniausia stogo kiekių klaida — skaičiuoti pagal plano plotą.
          Šlaitinio stogo tikrasis plotas visada didesnis:
        </P>
        <Callout title="Formulė">
          <P>
            <Code>stogo plotas = plano plotas × nuolydžio koeficientas</Code>
          </P>
        </Callout>
        <DefTable
          head={['Nuolydis', 'Koeficientas']}
          rows={[
            ['Plokščias (1–3°)', '1,00'],
            ['15°', '1,035'],
            ['30°', '1,155'],
            ['45°', '1,414'],
          ]}
        />
        <UL>
          <LI>Danga — tikrasis plotas + 8 % atliekų; hidroizoliacinė plėvelė — ×1,10.</LI>
          <LI>
            Plokščiam stogui: membrana ×1,15 (užlaidos ir užlenkimai ant
            parapetų), garo izoliacija ×1,10, parapetų skardinimas — pagal
            perimetrą.
          </LI>
          <LI>Latakai — karnizų perimetras; lietvamzdžiai — kas 10–12 m ir ties kampais.</LI>
        </UL>
      </Section>

      <Section n={4} title="Pastoliai ir bendrieji kiekiai">
        <P>
          Fasado darbai neįvyksta be pastolių, o pastoliai — dažna „paskutinės
          minutės“ eilutė, kuri pasiūlyme atsiranda apytiksliai ir vėliau
          skaudžiai tikslinasi:
        </P>
        <Callout title="Formulė">
          <P>
            <Code>pastolių plotas = fasado ilgis × (pastato aukštis + 2 m)</Code>
          </P>
        </Callout>
        <UL>
          <LI>
            Montavimas ir demontavimas — <Term>atskiros eilutės</Term>, ne
            nuomos kainos dalis.
          </LI>
          <LI>
            Nuomos trukmė siejama su darbų grafiku — fasado ciklas, ne
            kalendorinis mėnuo.
          </LI>
          <LI>
            Po langų keitimo — vidinių ir išorinių <Term>angokraščių
            apdaila</Term>: dar viena eilutė, kurią investicijų planai mini,
            o pasiūlymai pamiršta.
          </LI>
        </UL>
      </Section>

      <Section n={5} title="Atvirkštinis PVM — renovacijos ypatybė">
        <P>
          Statybos darbams Lietuvoje taikomas <Term>atvirkštinis PVM
          apmokestinimas</Term> (PVM įstatymo 96 str.): kai užsakovas yra PVM
          mokėtojas, rangovas sąskaitą išrašo be PVM, o mokestį deklaruoja ir
          sumoka pirkėjas. Daugiabučių modernizavimo projektuose tai —
          kasdienybė, todėl sąmatos PVM eilutė turi būti suformuota teisingai
          nuo pat pasiūlymo.
        </P>
        <P>
          Pathon sąmatose renovacijos projektams PVM eilutė formuojama
          atvirkštiniu būdu, standartiniams — įprastas 21 %. Prieš teikdami
          pasiūlymą įsitikinkite, kuri tvarka taikoma jūsų užsakovui.
        </P>
      </Section>

      <Section n={6} title="Investicijų plano formatas">
        <P>
          APVA administruojamoje daugiabučių atnaujinimo programoje pasiūlymai
          siejami su <Term>investicijų planu</Term>: jame priemonės (fasado
          šiltinimas, stogo šiltinimas, langų keitimas ir t. t.) išvardytos su
          kiekiais, įkainiais ir energinio efektyvumo tikslu (paprastai — ne
          žemesnė kaip B klasė ir apie 40 % energijos sutaupymas). Paramos
          dydžiai ir sąlygos keičiasi, todėl juos tikrinkite galiojančioje APVA
          tvarkoje.
        </P>
        <P>
          Rangovui praktinė išvada paprasta: <Term>pasiūlymo kiekiai turi
          atitikti investicijų plano priemonių struktūrą</Term> — kitaip
          pasiūlymo palyginti neįmanoma ir jis grąžinamas taisyti. Kiekių
          žiniaraštis pagal dalis (fasadas, stogas, cokolis, laiptinės,
          inžinerija) yra to pagrindas.
        </P>
      </Section>

      <Section n={7} title="Kaip tai padaryti per dieną">
        <P>
          Didžioji renovacijos pasiūlymo laiko dalis — ne kainodara, o kiekiai.
          Su <Link to="/about" className="text-primary hover:underline">Pathon</Link>{' '}
          darbas atrodo taip:
        </P>
        <UL>
          <LI>
            Įkeliate projekto PDF — sistema <Term>nuskaito esamas kiekių
            žiniaraščio lenteles</Term> iš visų dalių: eilutės su vienetais ir
            kiekiais perkeliamos į sąmatą, belieka įkainiai.
          </LI>
          <LI>
            <Term>Laiptinių ir kitų vidaus patalpų apdailą</Term> sistema
            apskaičiuoja giliausiai — nuo dažomų plotų iki glaisto kiekių pagal
            Q lygį (formulės —{' '}
            <Link to="/vidaus-apdailos-samata" className="text-primary hover:underline">
              vidaus apdailos sąmatos gide
            </Link>).
          </LI>
          <LI>
            Fasado ir stogo kiekiams taikomos pirmiau aprašytos normos pagal
            brėžinių matmenis — visos prielaidos matomos ir keičiamos, o
            kiekvienas kiekis turi pasitikėjimo indikatorių.
          </LI>
          <LI>
            Eksportuojate į Excel (su gyvomis formulėmis) arba PDF — sąmatą
            Lietuvos formatu su teisinga PVM eilute.
          </LI>
        </UL>
        <Callout title="Sąžininga riba">
          <P>
            Automatika neperima atsakomybės už pasiūlymą: prieš teikdami
            patikrinkite kiekius (sistema parodo, kuriuos pirmiausia) ir
            sutikrinkite priemones su investicijų planu. Kaip nuskaitymas
            veikia žingsnis po žingsnio —{' '}
            <Link to="/kiekiai-is-brezinio" className="text-primary hover:underline">
              kiekiai iš PDF brėžinio
            </Link>, dažni klausimai —{' '}
            <Link to="/duk" className="text-primary hover:underline">DUK</Link>.
          </P>
        </Callout>
      </Section>
    </MarketingLayout>
  );
}
