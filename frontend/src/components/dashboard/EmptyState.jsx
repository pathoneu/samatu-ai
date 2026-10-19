import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { useTranslation } from '@/i18n/react';
import { FileUp, Zap, Clock, CheckCircle2, Eye, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { seedDemoProject, DEMO_PROJECT_ID } from '@/lib/projectStore';

export default function EmptyState() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [loadingDemo, setLoadingDemo] = useState(false);

  const openDemo = async () => {
    setLoadingDemo(true);
    try {
      await seedDemoProject();
      navigate(`/project/${DEMO_PROJECT_ID}`);
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
        {t('dashboard.empty.title')}
      </h2>
      <p className="text-muted-foreground text-center max-w-md mb-8">
        {t('dashboard.empty.body')}
      </p>

      <div className="flex flex-col sm:flex-row items-center gap-3">
        <Link to="/new-project">
          <Button size="lg" className="bg-primary hover:bg-primary/90 text-primary-foreground font-semibold px-8">
            <FileUp className="w-5 h-5 mr-2" />
            {t('dashboard.empty.newProject')}
          </Button>
        </Link>
        <Button
          size="lg"
          variant="outline"
          onClick={openDemo}
          disabled={loadingDemo}
          title={t('dashboard.empty.viewDemoTitle')}
          className="font-medium px-6"
        >
          {loadingDemo
            ? <Loader2 className="w-5 h-5 mr-2 animate-spin" />
            : <Eye className="w-5 h-5 mr-2" />}
          {t('dashboard.empty.viewDemo')}
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-12 max-w-2xl">
        {[
          { icon: Zap, title: t('dashboard.empty.feat1Title'), desc: t('dashboard.empty.feat1Desc') },
          { icon: Clock, title: t('dashboard.empty.feat2Title'), desc: t('dashboard.empty.feat2Desc') },
          { icon: CheckCircle2, title: t('dashboard.empty.feat3Title'), desc: t('dashboard.empty.feat3Desc') },
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