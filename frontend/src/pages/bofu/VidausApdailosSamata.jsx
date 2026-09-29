/**
 * /vidaus-apdailos-samata — BoFu landing page (docs/marketing/seo-playbook.md §3.3).
 * Trade/authority page: realios vidaus apdailos formulės iš CLAUDE.md §1
 * (dažomas plotas, angokraščiai, glaistas pagal Q, GKP) — gylis, kurio LT
 * konkurentai neturi.
 *
 * ⚠️ JUODRAŠTIS (2026-07-06): visą LT tekstą prieš publikavimą peržiūri ir
 * nušlifuoja founderis (LT copy rule: Claude drafts → founder polishes → publish).
 * Formulės ir normos — iš vidinės žinių bazės (NRM2, DIN 18363, Merkblatt Nr. 2);
 * skaičiai sutikrinti su CLAUDE.md §1, bet paskutinį žodį taria founderis.
 *
 * Schema: Article + HowTo (matomi žingsniai 7 sekcijoje — vienintelis šaltinis).
 */
import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import MarketingLayout from '@/components/marketing/MarketingLayout';
import {
  Section, SubHead, P, Term, UL, LI, Callout, Code, DefTable,
} from '@/components/legal/LegalLayout';
import { setPageMeta, setJsonLd } from '@/lib/seo';

const PATH = '/vidaus-apdailos-samata';
const URL = `https://pathon.eu${PATH}`;

// Single source of truth: renders the visible step-by-step section AND the
// HowTo JSON-LD — the two can never drift apart.
const HOWTO_STEPS = [
  {
    name: 'Išmatuokite patalpas',
    text: 'Kiekvienai patalpai reikia perimetro, grindų ploto ir lubų aukščio. Turint projekto PDF, šiuos dydžius galima nuskaityti automatiškai.',
  },
  {
    name: 'Suskaičiuokite angas ir zonas',
    text: 'Langai, durys, plytelių zonos, įmontuoti baldai — visa tai atimama iš dažomo ploto. Angos, mažesnės nei 0,5 m², neatimamos.',
  },
  {
    name: 'Pritaikykite formules',
    text: 'Dažomas plotas = perimetras × aukštis − angos + angokraščiai. Glaistas — pagal Q lygį ir storį, dažai — pagal išeigą ir sluoksnius, GKP — po 3 m² lapui su 10 % atliekų.',
  },
  {
    name: 'Pridėkite paruošimo ir pagalbines eilutes',
    text: 'Gruntavimas, glaistymo kampai, hidroizoliacija šlapiose zonose, grindjuostės — atskiros eilutės, kurias lengviausia pamiršti.',
  },
  {
    name: 'Suveskite įkainius ir PVM',
    text: 'Prie kiekių pridedami jūsų darbų ir medžiagų įkainiai, tada 21 % PVM (renovacijai — atvirkštinis apmokestinimas).',
  },
];

export default function VidausApdailosSamata() {
  useEffect(() => {
    setPageMeta({
      title: 'Vidaus apdailos sąmata — kaip paskaičiuoti kiekius',
      description:
        'Vidaus apdailos sąmatos formulės: dažomas plotas, angokraščiai, glaistas pagal Q1–Q4, gipso kartono lapai — ir kaip kiekius paskaičiuoti automatiškai.',
      path: PATH,
    });
    setJsonLd('jsonld-article-apdaila', {
      '@context': 'https://schema.org',
      '@type': 'Article',
      '@id': `${URL}#article`,
      headline: 'Vidaus apdailos sąmata: formulės, kurias naudoja profesionalai',
      description:
        'Dažomo ploto, angokraščių, glaistymo pagal Q1–Q4 ir gipso kartono kiekių formulės vidaus apdailos sąmatai — su normomis ir dažniausiomis klaidomis.',
      inLanguage: 'lt',
      mainEntityOfPage: URL,
      image: 'https://pathon.eu/og-image.png',
      datePublished: '2026-07-06',
      dateModified: '2026-07-06',
      author: { '@id': 'https://pathon.eu/#org' },
      publisher: { '@id': 'https://pathon.eu/#org' },
    });
    setJsonLd('jsonld-howto-apdaila', {
      '@context': 'https://schema.org',
      '@type': 'HowTo',
      name: 'Kaip paskaičiuoti vidaus apdailos sąmatą',
      description:
        'Penki žingsniai nuo patalpų matmenų iki vidaus apdailos sąmatos su PVM.',
      inLanguage: 'lt',
      step: HOWTO_STEPS.map(({ name, text }, i) => ({
        '@type': 'HowToStep',
        position: i + 1,
        name,
        text,
      })),
    });
    return () => {
      document.getElementById('jsonld-article-apdaila')?.remove();
      document.getElementById('jsonld-howto-apdaila')?.remove();
    };
  }, []);

  return (
    <MarketingLayout
      eyebrow="Gidas / Apdaila"
      index="GID-03"
      title="Vidaus apdailos sąmata: formulės, kurias naudoja profesionalai"
      intro="Dažomas plotas, angokraščiai, glaistas pagal Q lygius, gipso kartonas — konkrečios formulės ir normos, be kurių apdailos sąmata lieka spėjimu."
      updated="2026-07-06"
      related={[
        { to: '/kiekiai-is-brezinio', label: 'Kiekiai iš PDF brėžinio' },
        { to: '/apva-renovacijos-kiekiai', label: 'APVA renovacijos kiekiai' },
        { to: '/duk', label: 'DUK' },
      ]}
    >
      <Section n={1} title="Dažomas plotas">
        <Callout title="Formulė">
          <P>
            <Code>S sienų = perimetras × lubų aukštis − angos + angokraščiai</Code>
          </P>
          <P>
            <Code>S lubų = grindų plotas</Code> (lygioms luboms; kitaip — iš lubų
            plano)
          </P>
        </Callout>
        <P>
          Iš bendro sienų ploto atimami langai, durys, plytelių zonos ir
          įmontuotų baldų plotai. Kelios taisyklės, skiriančios profesionalią
          sąmatą nuo skaičiavimo „iš akies“:
        </P>
        <UL>
          <LI>
            Angos, mažesnės nei <Term>0,5 m²</Term>, neatimamos — tokia
            tarptautinė kiekių skaičiavimo praktika (NRM2).
          </LI>
          <LI>
            <Term>Sienos ir lubos — atskiros eilutės.</Term> Skirtingi dažai,
            skirtingi įkainiai, skirtinga darbo sparta.
          </LI>
          <LI>
            <Term>Gruntavimas — atskira eilutė</Term>, ne „įskaičiuota į
            dažymą“. Kiekvienas dažų sluoksnis — atskiras kiekis.
          </LI>
        </UL>
        <P>
          Greita savikontrolė: dažomas sienų plotas paprastai būna{' '}
          <Term>2,5–4 kartus didesnis už grindų plotą</Term>. Jei jūsų skaičius
          iškrenta iš šio intervalo — kažkur klaida.
        </P>
      </Section>

      <Section n={2} title="Angokraščiai — eilutė, kurią pamiršta dažniausiai">
        <Callout title="Formulė">
          <P>
            <Code>ilgis = 2 × angos aukštis + angos plotis</Code> (kiekvienai
            angai)
          </P>
          <P>
            <Code>plotas = ilgis × sienos storis</Code>
          </P>
        </Callout>
        <P>
          Standartinis 1,2 × 1,5 m langas duoda apie <Term>4–5 m
          angokraščių</Term> — juos reikia glaistyti, gruntuoti ir dažyti, o
          darbo sąnaudos metrui yra didesnės nei lygiai sienai. Bute su 6–8
          langais ir durimis susidaro dešimtys metrų — praleidus šią eilutę,
          sąmata „nesueina“ jau objekte.
        </P>
      </Section>

      <Section n={3} title="Glaistymas pagal Q lygius">
        <P>
          Kiek glaisto reikia, priklauso ne nuo noro, o nuo pasirinktos
          paviršiaus kokybės klasės (Q1–Q4) ir sluoksnio storio:
        </P>
        <DefTable
          head={['Lygis', 'Kam naudojamas', 'Sąnaudos', 'Tipinis storis']}
          rows={[
            ['Q1', 'po storais tapetais', '0,8 kg/m²/mm', '0,5–1 mm'],
            ['Q2', 'po matiniais dažais', '1,0 kg/m²/mm', '1–1,5 mm'],
            ['Q3', 'po pusiau blizgiais dažais', '1,2 kg/m²/mm', '1,5–2 mm'],
            ['Q4', 'po blizgiais dažais / laku', '1,5 kg/m²/mm', '3–5 mm (ištisinis)'],
          ]}
        />
        <Callout title="Formulė">
          <P>
            <Code>glaistas (kg) = plotas × storis (mm) × sąnaudos</Code>, maišai
            = kg ÷ 25, apvalinant į viršų.
          </P>
        </Callout>
        <P>
          Ir dažniausiai „pamirštama“ apdailos eilutė:{' '}
          <Term>Q4 šlifavimas — atskiras darbas</Term>, apie 0,3 val./m² (80–120
          grūdėtumas, 100 % paviršiaus). Vien šlifavimas sudaro apie 25–35 %
          viso GKP apdailos darbų kainos — sąmatos, kuriose jo nėra, objekte
          virsta nuostoliu.
        </P>
      </Section>

      <Section n={4} title="Dažų kiekis">
        <Callout title="Formulė">
          <P>
            <Code>dažai (l) = plotas × sluoksniai ÷ išeiga (m²/l)</Code>
          </P>
        </Callout>
        <DefTable
          head={['Paviršius', 'Išeiga (m²/l sluoksniui)']}
          rows={[
            ['Anksčiau dažytas, lygus', '10–12'],
            ['Glaistytas Q2–Q3', '7–9'],
            ['Šviežias tinkas', '3–5'],
            ['Gruntas', '~7 (0,15 l/m²)'],
          ]}
        />
        <UL>
          <LI>
            Pirmas sluoksnis geria daugiau — dviem sluoksniams skaičiuokite
            koeficientą <Term>1,8</Term>, ne 2,0.
          </LI>
          <LI>Apvalinkite iki pilnų pakuočių — dažų partijos skiriasi atspalviu.</LI>
          <LI>
            Šiurkštiems paviršiams pridėkite 10–20 % atsargą, ne standartinius
            5–8 %.
          </LI>
        </UL>
      </Section>

      <Section n={5} title="Gipso kartonas (GKP)">
        <Callout title="Formulė">
          <P>
            <Code>lapai = plotas ÷ 3,0 × 1,10</Code> (lapas 1,2 × 2,5 m = 3 m²;
            +10 % atliekos)
          </P>
        </Callout>
        <UL>
          <LI>
            <Term>Sienoms 12,5 mm, luboms 9,5 mm</Term> — tai skirtingos
            eilutės. Suplakus į vieną skaičių, lapų kiekis išeina klaidingas.
          </LI>
          <LI>Drėgnoms zonoms — drėgmei atsparus (žalias) GKP.</LI>
          <LI>
            Vienam lapui — apie 30 sraigtų; siūlių glaistui — apie 5 kg kibiras
            12 m² plotui.
          </LI>
          <LI>
            Kampų profiliai — tik <Term>išoriniams</Term> kampams; vidiniams
            užtenka popierinės juostos.
          </LI>
        </UL>
        <P>
          Praktikos pastaba: dalis meistrų GKP angų <Term>neatima</Term> —
          matuoja kiaurai, nes išpjovos vis tiek virsta atliekomis ir pjovimo
          darbu. Abu būdai teisėti; svarbu sąmatoje aiškiai pasakyti, kuris
          naudojamas.
        </P>
      </Section>

      <Section n={6} title="Atliekų koeficientai — kiek pridėti prie neto kiekių">
        <P>
          Neto kiekis iš brėžinio nėra užsakymo kiekis. Prie kiekvienos
          medžiagos pridedamas atliekų koeficientas — pagal
          medžiagą ir klojimo raštą:
        </P>
        <DefTable
          head={['Medžiaga', 'Atliekos']}
          rows={[
            ['Dažai', '5–8 % (šiurkštiems paviršiams 10–20 %)'],
            ['Gipso kartonas', '10–15 %'],
            ['Plytelės (tiesus klojimas)', '5–10 %'],
            ['Plytelės (eglutė)', '10–15 %'],
            ['Plytelės (šešiakampės)', '15–17 %'],
            ['Laminatas / parketlentės', '5–10 % (eglute — 12 %)'],
            ['Tapetai', '10–15 % (priklauso nuo rašto žingsnio)'],
            ['Grindjuostės', '~10 %'],
          ]}
        />
        <P>
          Taisyklė paprasta: kuo smulkesnis elementas ir kuo įstrižesnis
          klojimas, tuo didesnės atliekos. Sąmatoje koeficientą verta rodyti
          atskirai — užsakovui aišku, už ką moka, o jums nelieka „iš kur tie
          papildomi 12 %?“ klausimų.
        </P>
      </Section>

      <Section n={7} title="Ko nepamiršti: eilutės, kurios „pames“ sąmatą">
        <UL>
          <LI>
            <Term>Hidroizoliacija šlapiose zonose</Term> — vonios grindys
            ištisai, sienų juosta ~30 cm, dušo zona iki lubų, kampų juostos.
            Skysta membrana — apie 1,5 kg/m², dviem sluoksniais.
          </LI>
          <LI>
            <Term>Paruošimo darbai</Term> — gruntavimas ir glaistymas kaip
            atskiros eilutės, ne „viskas įskaičiuota“.
          </LI>
          <LI>
            <Term>Skirtingi lubų aukščiai</Term> — koridoriaus 2,5 m ir
            svetainės 3,2 m negalima skaičiuoti vienu aukščiu.
          </LI>
          <LI>
            <Term>Dvigubos sienos</Term> — pertvara tarp dviejų patalpų dažoma
            iš abiejų pusių, bet tik po vieną kartą iš kiekvienos.
          </LI>
        </UL>
      </Section>

      <Section n={8} title="Kaip paskaičiuoti: žingsnis po žingsnio">
        {HOWTO_STEPS.map(({ name, text }, i) => (
          <React.Fragment key={name}>
            <SubHead>{`${i + 1}. ${name}`}</SubHead>
            <P>{text}</P>
          </React.Fragment>
        ))}
        <Callout title="Arba automatiškai">
          <P>
            <Link to="/about" className="text-primary hover:underline">Pathon</Link>{' '}
            1–4 žingsnius atlieka pats: nuskaito PDF brėžinį, pritaiko šias
            formules ir parengia kiekių žiniaraštį, prie kiekvienos reikšmės
            rodydamas vietą brėžinyje, iš kurios ji paimta. Jums lieka atsakyti
            į kelis klausimus, peržiūrėti kiekius ir suvesti kainas. Kaip tai atrodo praktiškai —{' '}
            <Link to="/kiekiai-is-brezinio" className="text-primary hover:underline">
              kiekiai iš PDF brėžinio
            </Link>.
          </P>
          <P>
            Sąžininga riba: formulės deterministinės ir atitinka sąmatininkų
            praktiką, tačiau rezultatas priklauso nuo brėžinio kokybės — todėl
            prieš komercinį pasiūlymą kiekius būtina peržiūrėti. Daugiau —{' '}
            <Link to="/duk" className="text-primary hover:underline">DUK</Link>.
          </P>
        </Callout>
      </Section>
    </MarketingLayout>
  );
}
