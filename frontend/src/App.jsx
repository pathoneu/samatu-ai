import { Toaster } from "@/components/ui/toaster"
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClientInstance } from '@/lib/query-client'
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import React from 'react';
import PageNotFound from './lib/PageNotFound';
import AppLayout from '@/components/layout/AppLayout';
import Dashboard from '@/pages/Dashboard';
import NewProject from '@/pages/NewProject';
import ProjectDetail from '@/pages/ProjectDetail';
import PriceLists from '@/pages/PriceLists';
import Settings from '@/pages/Settings';

class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(e) { return { error: e }; }
  render() {
    if (this.state.error) {
      return (
        <div className="p-8 max-w-2xl mx-auto">
          <h2 className="text-lg font-bold text-red-500 mb-2">Rendering klaida</h2>
          <pre className="text-xs bg-gray-900 text-red-300 p-4 rounded overflow-auto whitespace-pre-wrap">
            {this.state.error.message}
            {'\n\n'}
            {this.state.error.stack}
          </pre>
          <button onClick={() => this.setState({ error: null })} className="mt-4 px-4 py-2 bg-primary text-white rounded text-sm">
            Bandyti vėl
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function App() {
  return (
    <QueryClientProvider client={queryClientInstance}>
      <Router>
        <ErrorBoundary>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/new-project" element={<NewProject />} />
              <Route path="/project/:id" element={<ProjectDetail />} />
              <Route path="/price-lists" element={<PriceLists />} />
              <Route path="/settings" element={<Settings />} />
            </Route>
            <Route path="*" element={<PageNotFound />} />
          </Routes>
        </ErrorBoundary>
      </Router>
      <Toaster />
    </QueryClientProvider>
  )
}

export default App
