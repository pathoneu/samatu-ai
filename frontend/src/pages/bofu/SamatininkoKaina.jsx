/**
 * /samatininko-kaina — BoFu landing page (docs/marketing/seo-playbook.md §3.1).
 * Sells by naming the price the buyer already pays for sąmatininko paslaugos.
 *
 * ⚠️ JUODRAŠTIS (2026-07-06): visą LT tekstą prieš publikavimą peržiūri ir
 * nušlifuoja founderis (LT copy rule: Claude drafts → founder polishes → publish).
 * Ypač patikrinti: rinkos kainų intervalus lentelėse (orientaciniai, be šaltinių —
 * playbook prašo šaltinių; pridėti arba palikti „orientacinės“) ir DUK atsakymus.
 *
 * Schema: Article + FAQPage (matomas DUK blokas — vienintelis šaltinis abiem).
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
    q: 'Kiek kainuoja statybos sąmata Lietuvoje?',
    a: 'Tipinė sąmatininko paslaugų kaina 2026 m. — apie €200–500 už objektą: buto vidaus apdailos sąmata dažniausiai pigesnė, pilna individualaus namo sąmata su visomis dalimis — brangesnė. Galutinę kainą lemia projekto apimtis, dokumentacijos kokybė ir terminai.',
  },
  {
    q: 'Ar galiu sąmatą pasidaryti pats, be sąmatininko?',
    a: 'Taip — jei turite projekto brėžinius ir žinote savo įkainius. Daugiausiai laiko suryja ne kainodara, o kiekių skaičiavimas: plotai, perimetrai, angos, atliekų koeficientai. Šią techninę dalį galima automatizuoti — įrankis paskaičiuoja kiekius, o sprendimus dėl kainų ir technologijų priimate jūs.',
  },
  {
    q: 'Kiek kainuoja sąmata su Pathon?',
    a: 'Vienkartinis projektas — €12. „Pro“ planas — €49/mėn. (10 projektų per mėnesį), „Studio“ — €149/mėn. (35 projektai). Naujoms įmonėms pirmasis bandomasis projektas nemokamas. Kainos nurodytos be PVM.',
  },
];

export default function SamatininkoKaina() {
  useEffect(() => {
    setPageMeta({
      title: 'Sąmatininko kaina 2026 ir kada skaičiuoti pačiam',
      description:
        'Kiek kainuoja sąmatininko paslaugos Lietuvoje 2026 m.? Rinkos kainos, kas jas lemia, kada verta samdyti specialistą ir kada kiekius paskaičiuoti pačiam.',
      path: PATH,
    });
    setJsonLd('jsonld-article-samatininko-kaina', {
      '@context': 'https://schema.org',
      '@type': 'Article',
      '@id': `${URL}#article`,
      headline: 'Sąmatininko paslaugos: kiek kainuoja ir kada apsimoka skaičiuoti pačiam',
      description:
        'Sąmatininko paslaugų rinkos kainos Lietuvoje, kas jas lemia, kada verta samdyti specialistą, o kada statybos kiekius ir sąmatą pasiskaičiuoti pačiam.',
      inLanguage: 'lt',
      mainEntityOfPage: URL,
      image: 'https://pathon.eu/og-image.png',
      datePublished: '2026-07-06',
      dateModified: '2026-07-06',
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
      eyebrow="Gidas / Kainos"
      index="GID-01"
      title="Sąmatininko paslaugos: kiek kainuoja ir kada apsimoka skaičiuoti pačiam"
      intro="Rinkos kainos 2026 m., kas jas lemia ir sąžiningas atsakymas, kada verta mokėti specialistui, o kada sąmatą pasidaryti pačiam."
      updated="2026-07-06"
      related={[
        { to: '/kiekiai-is-brezinio', label: 'Kiekiai iš PDF brėžinio' },
        { to: '/vidaus-apdailos-samata', label: 'Vidaus apdailos sąmata' },
        { to: '/duk', label: 'DUK' },
      ]}
    >
      <Section n={1} title="Kiek kainuoja sąmatininko paslaugos 2026 m.">
        <P>
          Lietuvoje sąmatininko paslaugos tipiniam objektui dažniausiai kainuoja{' '}
          <Term>apie €200–500</Term>. Mažesnė buto apdailos sąmata gali kainuoti
          pigiau, o pilna individualaus namo sąmata su konstrukcijomis, inžinerija
          ir apdaila — daugiau. Prie kainos beveik visada prisideda ir laukimas:
          geri sąmatininkai užimti, todėl darbas paprastai atliekamas per kelias
          darbo dienas ar savaites, ne per valandą.
        </P>
        <DefTable
          head={['Paslauga', 'Orientacinė kaina', 'Įprastas terminas']}
          rows={[
            ['Buto vidaus apdailos sąmata', '€150–300', '2–5 d. d.'],
            ['Namo sąmata (visos dalys)', '€300–500 ir daugiau', '1–2 sav.'],
            ['Kiekių žiniaraštis iš brėžinių', '€100–250', '2–4 d. d.'],
            ['Valandinis įkainis', '€20–40/val.', '—'],
          ]}
        />
        <P className="text-[13px] text-muted-foreground">
          Kainos orientacinės — jos priklauso nuo objekto, regiono ir susitarimo.
          Intervalai atspindi įprastą rinkos praktiką, ne konkretaus tiekėjo
          kainoraštį.
        </P>
      </Section>

      <Section n={2} title="Kas lemia kainą">
        <UL>
          <LI>
            <Term>Apimtis ir dalių skaičius.</Term> Vien apdaila ar apdaila +
            konstrukcijos + elektra + santechnika — skirtingos darbo valandos.
          </LI>
          <LI>
            <Term>Dokumentacijos kokybė.</Term> Kai brėžiniuose trūksta matmenų,
            eksplikacijų ar išklotinių, sąmatininkas matuoja ir klausinėja — tai
            laikas, už kurį mokate.
          </LI>
          <LI>
            <Term>Skubumas.</Term> „Reikia rytoj“ beveik visada reiškia priedą
            prie kainos arba atsisakymą.
          </LI>
          <LI>
            <Term>Pakeitimai.</Term> Projektas pasikeitė — kiekius reikia
            perskaičiuoti. Dažnai tai atskirai apmokamas darbas, o kiekvienas
            ratas vėl trunka dienas.
          </LI>
        </UL>
        <P>
          Ir svarbiausia — kaina sumuojasi. Įmonei, kuri teikia 8–10 pasiūlymų
          per mėnesį, sąmatininko paslaugos virsta tūkstančiais eurų mėnesio
          sąnaudų (arba savaitėmis savininko vakarų), nors užsakymu virsta tik
          dalis tų pasiūlymų. Būtent todėl skaičiavimo savikaina — ne
          smulkmena, o konkurencinis veiksnys.
        </P>
      </Section>

      <Section n={3} title="Kada verta samdyti sąmatininką">
        <P>
          Sąžiningai: yra situacijų, kuriose žmogus-specialistas yra teisingas
          pasirinkimas, ir jokia programa to nepakeičia.
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
            <Term>Visiškai nėra laiko</Term> — net valandai peržiūrėti kiekius ir
            suvesti kainas. Tuomet perkate ne skaičiavimą, o galvos skausmo
            nebuvimą.
          </LI>
        </UL>
      </Section>

      <Section n={4} title="Kada apsimoka skaičiuoti pačiam">
        <P>
          Daugumai apdailos ir remonto įmonių sąmata — ne vienkartinis įvykis, o
          kassavaitinė rutina: pasiūlymai klientams, kurių dalis niekada nevirs
          užsakymu. Mokėti po kelis šimtus eurų už kiekvieną pasiūlymą ir laukti
          po savaitę — brangiausias įmanomas būdas pralaimėti konkurenciją dėl
          greičio. Skaičiuoti pačiam apsimoka, kai:
        </P>
        <UL>
          <LI>objektai kartojasi — butų ir namų apdaila, o ne unikalūs statiniai;</LI>
          <LI>pasiūlymą reikia pateikti šiandien ar rytoj, kol klientas dar „šiltas“;</LI>
          <LI>įkainius ir maržą norite valdyti patys, o ne perimti svetimus;</LI>
          <LI>sąmata reikalinga deryboms ir darbui, o ne formaliam dokumentui su parašu.</LI>
        </UL>
        <SubHead>Ką realiai kainuoja viena sąmata</SubHead>
        <DefTable
          head={['Būdas', 'Pinigai', 'Jūsų laikas', 'Terminas']}
          rows={[
            ['Sąmatininkas', '€200–500', '~1 val. (perduoti projektą)', '2 d. d. – 2 sav.'],
            ['Pačiam „ranka“ (PDF + Excel)', '€0', '4–12 val. matavimų ir lentelių', '1–2 dienos'],
            ['Su Pathon', 'nuo €12', '~1 val. peržiūrai ir kainoms', '~15 min. skaičiavimas'],
          ]}
        />
        <P>
          <Link to="/" className="text-primary hover:underline">Pathon</Link>{' '}
          automatizuoja būtent tą dalį, kuri suryja valandas: nuskaito PDF
          brėžinį, atpažįsta patalpas ir elementus, paskaičiuoja kiekius pagal
          Lietuvos sąmatininkų praktiką ir parengia kiekių žiniaraštį. Kaip tai
          veikia žingsnis po žingsnio —{' '}
          <Link to="/kiekiai-is-brezinio" className="text-primary hover:underline">
            kiekiai iš PDF brėžinio
          </Link>.
        </P>
      </Section>

      <Section n={5} title="Trys būdai sumažinti sąmatų kaštus jau šį mėnesį">
        <UL>
          <LI>
            <Term>Susikurkite savo įkainių katalogą.</Term> Didžioji derybų su
            sąmatininku (ar su savimi) dalis — „kiek čia dėti už kvadratą?“.
            Vieną kartą susirašyti savo darbų įkainius ir juos perpanaudoti —
            valandų sutaupymas kiekviename pasiūlyme.
          </LI>
          <LI>
            <Term>Automatizuokite kiekius, ne sprendimus.</Term> Kiekiai —
            mechaninis darbas su aiškiomis taisyklėmis; būtent jį verta
            atiduoti programai. Kainodara ir pasiūlymo strategija lieka žmogui.
          </LI>
          <LI>
            <Term>Perskaičiavimus darykite prielaidomis, ne iš naujo.</Term>{' '}
            Projektai keičiasi visada. Jei pakeitus lubų aukštį ar glaistymo
            lygį sąmata persiskaičiuoja pati, pakeitimas kainuoja minutę, o ne
            dar vieną apmokamą ratą.
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
            sistemoje turi pasitikėjimo indikatorių: žalias — nuskaityta tiesiai
            iš brėžinio, geltonas — su prielaidomis, raudonas — numatytoji
            reikšmė. Prieš komercinį pasiūlymą kiekius reikia peržiūrėti.
          </LI>
          <LI>
            <Term>Atsakomybės.</Term> Už pateiktą pasiūlymą atsakote jūs — kaip
            ir naudodami bet kokį kitą skaičiavimo įrankį.
          </LI>
        </UL>
        <Callout title="Sąžininga riba">
          <P>
            Pathon tikslas — kad techninė kiekių dalis truktų minutes, o ne
            dienas. Ekspertizės, atsakomybės ir derybų jis neperima. Daugiau
            atsakymų — <Link to="/duk" className="text-primary hover:underline">DUK puslapyje</Link>.
          </P>
        </Callout>
      </Section>

      <Section n={7} title="Dažni klausimai apie sąmatos kainą">
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
