/**
 * /project/:id/annotator — fixture-aware page route. Just builds a PDF URL
 * from search params and mounts the reusable <AnnotatorView />. The viewer
 * itself (toolbar, canvas, sidebar, persistence) lives in
 * components/annotator/AnnotatorView.jsx and is shared with InteriorProject.
 */
import React from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import AnnotatorView from '@/components/annotator/AnnotatorView';

export default function Annotator() {
  const { id: projectId } = useParams();
  const [searchParams] = useSearchParams();
  const fixture = searchParams.get('fixture');
  const pdfOverride = searchParams.get('pdf');
  const initialPage = Number(searchParams.get('page') || 2);
  const pdfUrl = pdfOverride
    || (fixture
        ? `/api/projects/${projectId}/pdf?fixture=${fixture}`
        : `/api/projects/${projectId}/pdf`);
  return (
    <AnnotatorView
      projectId={projectId}
      fixture={fixture}
      pdfUrl={pdfUrl}
      initialPage={initialPage}
    />
  );
}
