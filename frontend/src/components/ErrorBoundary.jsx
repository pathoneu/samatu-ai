/**
 * ErrorBoundary — top-level React error boundary that catches render errors
 * and reports them to backend /api/log-error.
 *
 * Class component (React requires class for componentDidCatch as of v19).
 */

import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });

    // Best-effort report to backend (don't block on failure)
    try {
      fetch('/api/log-error', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: error?.message || 'Unknown render error',
          stack: error?.stack || errorInfo?.componentStack || '',
          component: errorInfo?.componentStack?.split('\n')[1]?.trim() || 'unknown',
          url: window.location.href,
          user_agent: navigator.userAgent,
        }),
      }).catch(() => { /* swallow — we already have an error */ });
    } catch { /* swallow */ }

    console.error('[ErrorBoundary] caught:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ error: null, errorInfo: null });
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center p-6 bg-background">
          <div className="max-w-md w-full border border-destructive/30 bg-destructive/5 rounded-xl p-6">
            <div className="flex items-start gap-3 mb-4">
              <AlertTriangle className="w-6 h-6 text-destructive shrink-0 mt-0.5" />
              <div>
                <h1 className="text-lg font-semibold text-foreground mb-1">
                  Įvyko netikėta klaida
                </h1>
                <p className="text-sm text-muted-foreground">
                  Aplikacija sutiko klaidą ir negali tęsti. Klaida automatiškai
                  pranešta serveriui — nereikia nieko siųsti rankiniu būdu.
                </p>
              </div>
            </div>

            <details className="mb-4 text-xs">
              <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                Klaidos detalės
              </summary>
              <pre className="mt-2 p-3 bg-muted rounded text-[11px] overflow-x-auto whitespace-pre-wrap break-words">
                {this.state.error?.message}
                {this.state.error?.stack ? '\n\n' + this.state.error.stack : ''}
              </pre>
            </details>

            <div className="flex gap-2">
              <Button variant="default" size="sm" onClick={this.handleReload}>
                Perkrauti puslapį
              </Button>
              <Button variant="outline" size="sm" onClick={this.handleReset}>
                Bandyti dar kartą
              </Button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
