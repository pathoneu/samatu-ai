/**
 * M5 (2026-05-06) — public landing page.
 *
 * Shown at "/" for unauthenticated visitors. Authenticated users get
 * redirected to /dashboard via the wrapper in App.jsx.
 *
 * Goals:
 * - Communicate what the app does in <10 seconds
 * - Build trust (LT, real screenshots, clear pricing intent)
 * - Single CTA: register / login
 */
import { Link } from 'react-router-dom';
import Logo from '@/components/layout/Logo';
import { ArrowRight, FileText, Calculator, Sparkles, ShieldCheck } from 'lucide-react';

export default function Landing() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="px-6 py-4 flex items-center justify-between border-b border-border">
        <Logo />
        <nav className="flex items-center gap-3 text-sm">
          <Link to="/login" className="text-muted-foreground hover:text-foreground transition-colors">
            Prisijungti
          </Link>
          <Link
            to="/register"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors font-medium"
          >
            Pradėti
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </nav>
      </header>

      <section className="max-w-5xl mx-auto px-6 py-20 text-center">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 mb-6 rounded-full bg-primary/10 border border-primary/20 text-xs font-medium text-primary">
          <Sparkles className="w-3 h-3" />
          Beta · Lietuvių statybos sąmatininkams
        </div>
        <h1 className="text-4xl md:text-6xl font-bold tracking-tight mb-5 leading-tight">
          Sąmatos per <span className="text-primary">minutes</span>,
          <br /> ne dienas
        </h1>
        <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-9">
          Įkelkite interjero projekto PDF — gausite kiekių žiniaraštį su
          dažomais plotais, plytelėmis, grindjuostėmis ir GKP kiekiais.
          Kiekvieną poziciją galite peržiūrėti, koreguoti ir patvirtinti.
        </p>
        <div className="flex items-center justify-center gap-3">
          <Link
            to="/register"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors font-semibold"
          >
            Sukurti paskyrą — nemokama
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            to="/login"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-md border border-border hover:bg-muted/40 transition-colors font-medium"
          >
            Jau turiu paskyrą
          </Link>
        </div>
        <p className="text-xs text-muted-foreground mt-6">
          Be mokėjimo · Be limitų beta laikotarpiu · LT kalbos UI
        </p>
      </section>

      <section className="max-w-5xl mx-auto px-6 py-12 grid md:grid-cols-3 gap-6">
        <FeatureCard
          icon={<FileText className="w-5 h-5" />}
          title="Skaito jūsų brėžinius"
          body="Atpažįsta eksplikaciją, lubų planus, sienų išklotines, pjūvius. Kambariai, plotai, perimetrai, durys, langai — paimama tiesiai iš PDF."
        />
        <FeatureCard
          icon={<Calculator className="w-5 h-5" />}
          title="LT industrijos formulės"
          body="Kiekiai skaičiuojami pagal RICS NRM2, DIN 18363, Knauf Q-sistemą + lietuvišką STR praktiką. Kiekviena pozicija turi šaltinio žymę."
        />
        <FeatureCard
          icon={<ShieldCheck className="w-5 h-5" />}
          title="AI ruošia, jūs patvirtinate"
          body="AI nepateikia nieko be jūsų peržiūros. Kiekvieną kambario plotą, kiekio pozicija, langą — galite peržiūrėti, redaguoti, patvirtinti."
        />
      </section>

      <section className="border-t border-border bg-muted/20">
        <div className="max-w-5xl mx-auto px-6 py-16 text-center">
          <h2 className="text-2xl md:text-3xl font-semibold mb-4">
            Kam tai naudinga?
          </h2>
          <div className="grid md:grid-cols-2 gap-8 mt-10 text-left">
            <div>
              <h3 className="font-semibold mb-2">Statybos rangovams</h3>
              <p className="text-sm text-muted-foreground">
                Greitai parengsite pasiūlymą klientui. Kiekiai jau apskaičiuoti
                pagal projektą — jums lieka įvesti vieneto kainas.
              </p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">Sąmatininkams</h3>
              <p className="text-sm text-muted-foreground">
                Sumažina rutiną — perimetras × aukštis, plotas + atliekos,
                sienos − angos. Visa tai padaroma iš karto. Jums lieka
                kontrolė ir ekspertizė.
              </p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">Interjero studijoms</h3>
              <p className="text-sm text-muted-foreground">
                Greitas atsakymas klientui apie preliminarią darbų vertę. Be
                ilgo skaičiavimo Excel'yje.
              </p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">Užsakovams</h3>
              <p className="text-sm text-muted-foreground">
                Galite patikrinti rangovų pateiktus skaičius — kiek tikrai
                yra dažomo ploto, plytelių, grindjuosčių jūsų projekte.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-3xl mx-auto px-6 py-16 text-center">
        <h2 className="text-2xl md:text-3xl font-semibold mb-4">
          Bandyti dabar
        </h2>
        <p className="text-muted-foreground mb-8">
          Beta laikotarpiu nemokama. Įkelkite vieną PDF — pamatysite, ar tai
          jums tinka.
        </p>
        <Link
          to="/register"
          className="inline-flex items-center gap-2 px-6 py-3 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors font-semibold"
        >
          Sukurti paskyrą
          <ArrowRight className="w-4 h-4" />
        </Link>
      </section>

      <footer className="border-t border-border mt-12">
        <div className="max-w-5xl mx-auto px-6 py-6 flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-muted-foreground">
          <div>© 2026 Pathon · Sąmatų AI</div>
          <div className="flex items-center gap-4">
            <Link to="/privacy" className="hover:underline">Privatumo politika</Link>
            <Link to="/terms" className="hover:underline">Naudojimo sąlygos</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, body }) {
  return (
    <div className="border border-border rounded-xl p-6 bg-card hover:shadow-sm transition-shadow">
      <div className="inline-flex items-center justify-center w-9 h-9 rounded-lg bg-primary/10 text-primary mb-4">
        {icon}
      </div>
      <h3 className="font-semibold mb-2">{title}</h3>
      <p className="text-sm text-muted-foreground leading-relaxed">{body}</p>
    </div>
  );
}
