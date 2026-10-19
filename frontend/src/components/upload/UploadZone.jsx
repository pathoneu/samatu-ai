import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from '@/i18n/react';
import { Upload, FileText, X } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * @param {object}   props
 * @param {Function} props.onFileSelect  called with the File, or null when cleared
 * @param {number}   props.resetToken    bump to clear the zone FROM THE OUTSIDE.
 *   The selected file lives in this component's own state, so a parent that
 *   rejects the file (preflight's "Pasirinkti kitą failą") could otherwise
 *   drop it while the zone kept showing the old filename.
 */
export default function UploadZone({
  onFileSelect, accept = '.pdf,.xlsx,.xls', label, resetToken = 0, onFilesSelect = null,
}) {
  // `onFilesSelect` (Pathon v3 W5-D, D14): several files at once — called with every accepted File in the
  // order chosen; the zone then shows the first name and how many more.
  const { t } = useTranslation();
  const resolvedLabel = label ?? t('upload.zone.defaultLabel');
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [moreFiles, setMoreFiles] = useState(0);
  const [fileError, setFileError] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!resetToken) return;   // 0 = initial mount, nothing to clear
    setSelectedFile(null);
    setFileError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [resetToken]);

  // Client-side guard so a wrong type / oversized file fails INSTANTLY instead
  // of after a ~30s server round-trip ending in a backend error. (2026-06-19)
  //
  // 200 MB, matching backend `MAX_PDF_SIZE_BYTES` (main.py:26). It used to be
  // 50 MB with copy that said so, which refused files the server would have
  // accepted — a contractor with a 120 MB scanned set was told his own drawing
  // was too big by a browser that never asked. (2026-09-04. The >50 MB
  // scale-hint skip in NewProject is a separate, deliberate guard and stays.)
  const MAX_BYTES = 200 * 1024 * 1024;
  const validateFile = useCallback((file) => {
    if (!file) return t('upload.zone.errNoFile');
    const allowed = accept.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
    const name = (file.name || '').toLowerCase();
    if (allowed.length && !allowed.some((ext) => name.endsWith(ext))) {
      return t('upload.zone.errBadFormat', { formats: allowed.join(', ') });
    }
    if (file.size > MAX_BYTES) {
      return t('upload.zone.errTooBig', { size: (file.size / 1024 / 1024).toFixed(1) });
    }
    return null;
  }, [accept, t]);

  const acceptFile = useCallback((file) => {
    const err = validateFile(file);
    if (err) { setFileError(err); return; }
    setFileError(null);
    setSelectedFile(file);
    setMoreFiles(0);
    onFileSelect(file);
  }, [validateFile, onFileSelect]);

  const acceptFiles = useCallback((list) => {
    const files = Array.from(list || []);
    if (!onFilesSelect || files.length < 2) { if (files[0]) acceptFile(files[0]); return; }
    const err = files.map(validateFile).find(Boolean);
    if (err) { setFileError(err); return; }
    setFileError(null);
    setSelectedFile(files[0]);
    setMoreFiles(files.length - 1);
    onFilesSelect(files);
  }, [validateFile, onFilesSelect, acceptFile]);

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragIn = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragOut = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files && files.length > 0) acceptFiles(files);
  }, [acceptFiles]);

  const handleChange = (e) => {
    if (e.target.files && e.target.files.length > 0) acceptFiles(e.target.files);
  };

  const clearFile = () => {
    setSelectedFile(null);
    setMoreFiles(0);
    onFileSelect(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const openFileDialog = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      openFileDialog();
    }
  }, [openFileDialog]);

  if (selectedFile) {
    return (
      <div className="border border-border rounded-xl bg-card p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <FileText className="w-5 h-5 text-primary" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-foreground truncate" title={selectedFile.name}>{selectedFile.name}{moreFiles > 0 ? ` ir dar ${moreFiles}` : ''}</p>
              <p className="text-xs text-muted-foreground">
                {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={clearFile}
            title={t('upload.zone.clearFile')}
            aria-label={t('upload.zone.clearFile')}
            className="p-2 hover:bg-secondary rounded-lg transition-colors"
          >
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={t('upload.zone.aria')}
      onDragOver={handleDrag}
      onDragEnter={handleDragIn}
      onDragLeave={handleDragOut}
      onDrop={handleDrop}
      onClick={openFileDialog}
      onKeyDown={handleKeyDown}
      className={cn(
        "border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:ring-offset-2",
        isDragging
          ? "border-primary bg-primary/5"
          : "border-border hover:border-primary/40 hover:bg-card"
      )}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept={accept}
        multiple={!!onFilesSelect}
        onChange={handleChange}
        className="sr-only"
        id="file-upload"
        tabIndex={-1}
      />
      <div aria-hidden="true">
        <div className="w-14 h-14 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto mb-4">
          <Upload className="w-7 h-7 text-primary" />
        </div>
        <p className="text-foreground font-medium mb-1">
          {t('upload.zone.dragPrefix')}<span className="text-primary">{t('upload.zone.dragChoose')}</span>
        </p>
        <p className="text-sm text-muted-foreground">{resolvedLabel}</p>
        <p className="text-xs text-muted-foreground mt-1">{t('upload.zone.maxSize')}</p>
      </div>
      {fileError && (
        <p className="text-sm font-medium text-red-700 mt-3" role="alert">{fileError}</p>
      )}
    </div>
  );
}
