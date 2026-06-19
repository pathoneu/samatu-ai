import React, { useCallback, useRef, useState } from 'react';
import { Upload, FileText, X } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function UploadZone({ onFileSelect, accept = '.pdf,.xlsx,.xls', label = 'PDF arba Excel failas' }) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileError, setFileError] = useState(null);
  const fileInputRef = useRef(null);

  // Client-side guard so a wrong type / oversized file fails INSTANTLY instead
  // of after a ~30s server round-trip ending in a backend error. (2026-06-19)
  const MAX_BYTES = 50 * 1024 * 1024;
  const validateFile = useCallback((file) => {
    if (!file) return 'Failas nepasirinktas.';
    const allowed = accept.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
    const name = (file.name || '').toLowerCase();
    if (allowed.length && !allowed.some((ext) => name.endsWith(ext))) {
      return `Netinkamas formatas. Tinka tik: ${allowed.join(', ')}.`;
    }
    if (file.size > MAX_BYTES) {
      return `Failas per didelis (${(file.size / 1024 / 1024).toFixed(1)} MB). Maksimumas 50 MB.`;
    }
    return null;
  }, [accept]);

  const acceptFile = useCallback((file) => {
    const err = validateFile(file);
    if (err) { setFileError(err); return; }
    setFileError(null);
    setSelectedFile(file);
    onFileSelect(file);
  }, [validateFile, onFileSelect]);

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
    if (files && files.length > 0) acceptFile(files[0]);
  }, [acceptFile]);

  const handleChange = (e) => {
    if (e.target.files && e.target.files.length > 0) acceptFile(e.target.files[0]);
  };

  const clearFile = () => {
    setSelectedFile(null);
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
            <div>
              <p className="text-sm font-medium text-foreground">{selectedFile.name}</p>
              <p className="text-xs text-muted-foreground">
                {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          </div>
          <button onClick={clearFile} className="p-2 hover:bg-secondary rounded-lg transition-colors">
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
      aria-label="Pasirinkti projekto failą"
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
          Vilkite failą čia arba <span className="text-primary">pasirinkite</span>
        </p>
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-xs text-muted-foreground mt-1">Maks. 50 MB</p>
      </div>
      {fileError && (
        <p className="text-sm font-medium text-red-700 mt-3" role="alert">{fileError}</p>
      )}
    </div>
  );
}
