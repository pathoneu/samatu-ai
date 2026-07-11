/**
 * /samatininko-kaina — BoFu landing page (docs/marketing/seo-playbook.md §3.1).
 *
 * ANGLE (2026-07-09, founder): the real cost of a sąmata is NOT money paid to
 * someone — most LT contractors do it themselves. The cost is HOURS out of
 * their day. So this page answers "kiek kainuoja / kiek laiko atima sąmata"
 * with the honest answer: your time. No "you pay a sąmatininkas €X" framing.
 *
 * ⚠️ JUODRAŠTIS: visą LT tekstą prieš publikavimą peržiūri founderis
 * (LT copy rule: Claude drafts → founder polishes → publish).
 *
 * Schema: Article + FAQPage (matomas DUK blokas — vienintelis šaltinis abiem).
 * NOTE: URL slug kept as /samatininko-kaina to avoid breaking sitemap/prerender;
 * content now targets time-cost intent ("kiek laiko atima sąmata", "sąmata pačiam").
 */
import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import MarketingLayout from '@/components/marketing/MarketingLayout';
import {
  Section, SubHead, P, Term, UL, LI, Callout, DefTable,
} from '@/components/legal/LegalLayout';
import { setPageMeta, setJsonLd } from '@/lib/seo';

const PATH = '/samatininko-kaina';
const URL = `https://pathon.eu${PATH}`;

// Single source of truth: renders the visible DUK section AND FAQPage JSON-LD.
const FAQ = [
  {
    q: 'Kiek laiko atima statybos sąmata?',
    a: 'Rankinis kiekių skaičiavimas iš brėžinių tipiniam objektui atima nuo kelių valandų iki poros dienų: reikia išmatuoti plotus ir perimetrus, suskaičiuoti angas, pritaikyti atliekų koeficientus ir viską suvesti į lentelę. Daugiausia laiko suryja ne kainodara, o būtent kiekių skaičiavimas.',
  },
  {
    q: 'Ar galiu sąmatą pasidaryti pats, be sąmatininko?',
    a: 'Taip — jei turite projekto brėžinius ir žinote savo įkainius. Daugiausia laiko suryja ne kainodara, o kiekių skaičiavimas: plotai, perimetrai, angos, atliekų koeficientai. Šią techninę dalį galima automatizuoti — įrankis apskaičiuoja kiekius, o sprendimus dėl kainų ir technologijų priimate jūs.',
  },
  {
    q: 'Kiek kainuoja sąmata su Pathon?',
    a: 'Vienkartinis projektas — 12 €. „Pro“ planas — 49 €/mėn. (10 projektų per mėnesį), „Studio“ — 149 €/mėn. (35 projektai). Naujoms įmonėms pirmasis bandomasis projektas nemokamas. Kainos nurodytos be PVM.',
  },
];

export default function SamatininkoKaina() {
  useEffect(() => {
    setPageMeta({
      title: 'Kiek laiko atima sąmata ir kaip skaičiuoti greičiau',
      description:
        'Kiek laiko atima statybos sąmatos skaičiavimas iš brėžinių, kur dingsta valandos ir kaip jį sutrumpinti nuo valandų iki minučių — patys, be sąmatininko.',
      path: PATH,
    });
    setJsonLd('jsonld-article-samatininko-kaina', {
      '@context': 'https://schema.org',
      '@type': 'Article',
      '@id': `${URL}#article`,
      headline: 'Kiek laiko atima sąmata — ir kaip ją skaičiuoti greičiau, patys',
      description:
        'Tikroji statybos sąmatos kaina — jūsų laikas. Kiek valandų atima kiekių skaičiavimas iš brėžinių, kur jos dingsta ir kaip skaičiavimą sutrumpinti iki minučių.',
      inLanguage: 'lt',
      mainEntityOfPage: URL,
      image: 'https://pathon.eu/og-image.png',
      datePublished: '2026-07-06',
      dateModified: '2026-07-09',
      author: { '@id': 'https://pathon.eu/#org' },
      publisher: { '@id': 'https://pathon.eu/#org' },
    });
    setJsonLd('jsonld-faq-samatininko-kaina', {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: FAQ.map(({ q, a }) => ({
        '@type': 'Question',
        name: q,
        acceptedAnswer: { '@type': 'Answer', text: a },
      })),
    });
    return () => {
      document.getElementById('jsonld-article-samatininko-kaina')?.remove();
      document.getElementById('jsonld-faq-samatininko-kaina')?.remove();
    };
  }, []);

  return (
    <MarketingLayout
      eyebrow="Gidas / Sąmatos"
      index="GID-01"
      title="Kiek laiko atima sąmata — ir kaip ją skaičiuoti greičiau"
      intro="Tikroji sąmatos kaina — ne pinigai kažkam, o valandos iš jūsų dienos. Kiek laiko atima kiekių skaičiavimas iš brėžinių ir kaip jį sutrumpinti nuo valandų iki minučių."
      updated="2026-07-09"
      related={[
        { to: '/kiekiai-is-brezinio', label: 'Kiekiai iš PDF brėžinio' },
        { to: '/vidaus-apdailos-samata', label: 'Vidaus apdailos sąmata' },
        { to: '/duk', label: 'DUK' },
      ]}
    >
      <Section n={1} title="Tikroji sąmatos kaina — jūsų laikas">
        <P>
          Dauguma statybos ir apdailos įmonių sąmatų niekam neužsako — jas
          skaičiuoja patys: savininkas ar meistras vakarais matuoja brėžinius ir
          veda lenteles. Todėl tikroji sąmatos kaina — ne pinigai kažkam, o{' '}
          <Term>valandos iš jūsų dienos</Term>. Vienam objektui rankinis kiekių
          skaičiavimas dažniausiai atima nuo kelių valandų iki poros dienų.
        </P>
        <DefTable
          head={['Būdas', 'Jūsų laikas', 'Terminas']}
          rows={[
            ['Rankinis skaičiavimas (PDF + Excel)', '4–12 val.', '1–2 dienos'],
            ['Su Pathon', '~1 val. (peržiūra + kainos)', '~15 min.'],
          ]}
        />
        <P className="text-[13px] text-muted-foreground">
          Skaičiai orientaciniai — priklauso nuo objekto apimties ir
          dokumentacijos kokybės.
        </P>
      </Section>

      <Section n={2} title="Kur dingsta valandos">
        <UL>
          <LI>
            <Term>Matavimai.</Term> Plotai, perimetrai, lubų aukščiai, angos —
            kiekvienas skaičius ranka iš brėžinio.
          </LI>
          <LI>
            <Term>Atliekos ir koeficientai.</Term> Kiekvienai medžiagai — savas
            priedas; lengva suklysti arba pamiršti.
          </LI>
          <LI>
            <Term>Dokumentacijos spragos.</Term> Kai brėžiniuose trūksta matmenų,
            eksplikacijų ar išklotinių, tenka spėlioti ir tikslintis — dar valandos.
          </LI>
          <LI>
            <Term>Pakeitimai.</Term> Pasikeitė projektas — kiekius skaičiuojate iš
            naujo. Kiekvienas ratas vėl trunka valandas.
          </LI>
        </UL>
        <P>
          Ir tai kartojasi. Įmonei, teikiančiai 8–10 pasiūlymų per mėnesį, sąmatų
          skaičiavimas virsta dešimtimis valandų per mėnesį — savaitėmis
          savininko vakarų — nors užsakymu virsta tik dalis pasiūlymų. Būtent
          todėl skaičiavimo greitis — ne smulkmena, o konkurencinis veiksnys.
        </P>
      </Section>

      <Section n={3} title="Kada vis dėlto verta kreiptis į specialistą">
        <P>
          Sąžiningai: yra atvejų, kai žmogus-specialistas — teisingas pasirinkimas,
          ir jokia programa jo nepakeičia.
        </P>
        <UL>
          <LI>
            <Term>Dideli ar nestandartiniai objektai</Term> — sudėtingos
            konstrukcijos, rekonstrukcijos su daug nežinomųjų, paveldo pastatai.
          </LI>
          <LI>
            <Term>Oficiali atsakomybė</Term> — teismo ekspertizės, ginčai su
            užsakovu ar rangovu, draudiminiai įvykiai, kur reikia specialisto
            parašo ir kvalifikacijos.
          </LI>
          <LI>
            <Term>Viešieji pirkimai</Term> su griežtais sąmatų formato ir
            normatyvų reikalavimais.
          </LI>
          <LI>
            <Term>Visai nėra laiko</Term> — net valandos peržiūrėti kiekiams ir
            suvesti kainoms. Tada darbą verta atiduoti visą.
          </LI>
        </UL>
      </Section>

      <Section n={4} title="Kaip sutrumpinti skaičiavimą nuo valandų iki minučių">
        <P>
          Daugumai apdailos ir remonto įmonių sąmata — ne vienkartinis įvykis, o
          kassavaitinė rutina: pasiūlymai klientams, kurių dalis niekada nevirs
          užsakymu. Praleisti po pusdienį prie kiekvieno pasiūlymo ir pateikti jį
          tik po savaitės — brangiausias būdas pralaimėti konkurenciją dėl greičio.
        </P>
        <P>
          <Link to="/about" className="text-primary hover:underline">Pathon</Link>{' '}
          automatizuoja būtent tą dalį, kuri suryja valandas: nuskaito PDF brėžinį,
          atpažįsta patalpas ir elementus, paskaičiuoja kiekius pagal Lietuvos
          praktiką ir parengia kiekių žiniaraštį. Jums lieka peržiūrėti pažymėtas
          vietas ir suvesti savo įkainius. Kaip tai veikia žingsnis po žingsnio —{' '}
          <Link to="/kiekiai-is-brezinio" className="text-primary hover:underline">
            kiekiai iš PDF brėžinio
          </Link>.
        </P>
      </Section>

      <Section n={5} title="Trys būdai skaičiuoti greičiau jau šį mėnesį">
        <UL>
          <LI>
            <Term>Susikurkite savo įkainių katalogą.</Term> Didžioji laiko dalis
            dingsta ties klausimu „kiek čia dėti už kvadratą?“. Vieną kartą
            surašykite savo darbų įkainius ir juos perpanaudokite — valandos
            sutaupomos kiekviename pasiūlyme.
          </LI>
          <LI>
            <Term>Automatizuokite kiekius, ne sprendimus.</Term> Kiekiai —
            mechaninis darbas su aiškiomis taisyklėmis; būtent jį verta atiduoti
            programai. Kainodara ir pasiūlymo strategija lieka jums.
          </LI>
          <LI>
            <Term>Perskaičiavimus darykite prielaidomis, ne iš naujo.</Term>{' '}
            Projektai keičiasi visada. Jei pakeitus lubų aukštį ar glaistymo lygį
            sąmata persiskaičiuoja pati, pakeitimas kainuoja minutę, o ne dar vieną
            pusdienį.
          </LI>
        </UL>
      </Section>

      <Section n={6} title="Ko įrankis nepadaro">
        <P>
          Kad sprendimas būtų pagrįstas, o ne reklaminis, — štai ko automatinis
          skaičiavimas <Term>neatstoja</Term>:
        </P>
        <UL>
          <LI>
            <Term>Kainodaros sprendimų.</Term> Įkainiai, marža, nuolaidos ir
            pasiūlymo strategija lieka jums — programa kainų už jus nesugalvoja.
          </LI>
          <LI>
            <Term>Projekto klaidų tikrinimo.</Term> Jei brėžinyje klaida, jos
            programa neaptiks taip, kaip patyręs specialistas.
          </LI>
          <LI>
            <Term>Šimtaprocentinio atpažinimo.</Term> Simbolių ir elementų
            nuskaitymas iš brėžinių nėra tobulas, todėl kiekvienas kiekis Pathon
            sistemoje turi pasitikėjimo indikatorių: žalias — nuskaityta tiesiai iš
            brėžinio, geltonas — su prielaidomis, raudonas — numatytoji reikšmė.
            Prieš komercinį pasiūlymą kiekius reikia peržiūrėti.
          </LI>
          <LI>
            <Term>Atsakomybės.</Term> Už pateiktą pasiūlymą atsakote jūs — kaip ir
            naudodami bet kokį kitą skaičiavimo įrankį.
          </LI>
        </UL>
        <Callout title="Sąžininga riba">
          <P>
            Pathon tikslas — kad techninė kiekių dalis truktų minutes, o ne dienas.
            Ekspertizės, atsakomybės ir derybų jis neperima. Daugiau atsakymų —{' '}
            <Link to="/duk" className="text-primary hover:underline">DUK puslapyje</Link>.
          </P>
        </Callout>
      </Section>

      <Section n={7} title="Dažni klausimai apie sąmatos skaičiavimą">
        {FAQ.map(({ q, a }) => (
          <React.Fragment key={q}>
            <SubHead>{q}</SubHead>
            <P>{a}</P>
          </React.Fragment>
        ))}
      </Section>
    </MarketingLayout>
  );
}
