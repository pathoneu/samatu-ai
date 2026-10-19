/**
 * „Atnaujinta iš serverio" — one compact notice when a page load replaced this browser's cached copy of the
 * project with the server's, because the server moved on since this browser last saw it (another tab or
 * device saved, a version was restored elsewhere) and what he sees changed (lib/projectStore.js
 * refreshProjectFromBackend, Pathon v3 W1-F F4). The load may finish after this mounts, so it also listens.
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw } from 'lucide-react';
import Notice from '@/components/ui/Notice';
import {
  SERVER_REFRESH_EVENT, dismissServerRefreshNotice, hasServerRefreshNotice,
} from '@/lib/projectStore';

export default function ServerRefreshNotice({ projectId }) {
  const { t } = useTranslation();
  const [shown, setShown] = useState(() => !!projectId && hasServerRefreshNotice(projectId));
  useEffect(() => {
    if (!projectId) return undefined;
    setShown(hasServerRefreshNotice(projectId));
    const on = (e) => { if (e?.detail?.id === projectId) setShown(true); };
    window.addEventListener(SERVER_REFRESH_EVENT, on);
    return () => window.removeEventListener(SERVER_REFRESH_EVENT, on);
  }, [projectId]);
  if (!shown) return null;
  return (
    <div className="mt-3">
      <Notice
        compact
        tone="info"
        icon={RefreshCw}
        title={t('project.serverRefresh.title')}
        onDismiss={() => { dismissServerRefreshNotice(projectId); setShown(false); }}
        dismissLabel={t('project.serverRefresh.dismiss')}
        data-testid="server-refresh-notice"
      >
        {t('project.serverRefresh.body')}
      </Notice>
    </div>
  );
}
