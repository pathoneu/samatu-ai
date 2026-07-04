import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FileUp, Zap, Clock, CheckCircle2, Eye, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { seedDemoProject } from '@/lib/projectStore';

export default function EmptyState() {
  const navigate = useNavigate();
  const [loadingDemo, setLoadingDemo] = useState(false);

  const openDemo = async () => {
    setLoadingDemo(true);
    try {
      await seedDemoProject();
      navigate('/project/demo-berzu-24');
    } finally {
      setLoadingDemo(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center py-20 px-4">
      <div className="w-20 h-20 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-6">
        <FileUp className="w-10 h-10 text-primary" />
      </div>
      <h2 className="text-xl font-semibold text-foreground mb-2">
        Dar nėra projektų
      </h2>
      <p className="text-muted-foreground text-center max-w-md mb-8">
        Įkelkite statybų projekto brėžinį (PDF) — Pathon nuskaitys ir
        apskaičiuos kiekius bei paruoš sąmatą. Arba pirma apžiūrėkite
        pavyzdinį projektą.
      </p>

      <div className="flex flex-col sm:flex-row items-center gap-3">
        <Link to="/new-project">
          <Button size="lg" className="bg-primary hover:bg-primary/90 text-primary-foreground font-semibold px-8">
            <FileUp className="w-5 h-5 mr-2" />
            Naujas projektas
          </Button>
        </Link>
        <Button
          size="lg"
          variant="outline"
          onClick={openDemo}
          disabled={loadingDemo}
          className="font-medium px-6"
        >
          {loadingDemo
            ? <Loader2 className="w-5 h-5 mr-2 animate-spin" />
            : <Eye className="w-5 h-5 mr-2" />}
          Peržiūrėti pavyzdinį projektą
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-12 max-w-2xl">
        {[
          { icon: Zap, title: 'AI analizė', desc: 'Automatinis KŽ eilučių atpažinimas' },
          { icon: Clock, title: 'Sutaupykite laiką', desc: '1-2 savaitės darbo per kelias minutes' },
          { icon: CheckCircle2, title: 'Tiksli sąmata', desc: 'Realiu laiku skaičiavimai ir eksportas' },
        ].map(({ icon: Icon, title, desc }) => (
          <div key={title} className="text-center">
            <Icon className="w-5 h-5 text-primary mx-auto mb-2" />
            <p className="text-sm font-medium text-foreground">{title}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}