import { useCallback, useState, useRef } from 'react';
import { PdfFile } from '../types';

function generateId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for non-secure contexts
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

interface PdfDropzoneProps {
  onFilesAdded: (files: PdfFile[]) => void;
}

export default function PdfDropzone({ onFilesAdded }: PdfDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processFiles = useCallback(async (files: FileList | File[]) => {
    const pdfFiles: PdfFile[] = [];
    setIsProcessing(true);

    for (const file of Array.from(files)) {
      const isPdf = file.type === 'application/pdf' ||
                    file.name.toLowerCase().endsWith('.pdf');

      if (isPdf) {
        try {
          const arrayBuffer = await new Promise<ArrayBuffer>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result as ArrayBuffer);
            reader.onerror = () => reject(reader.error);
            reader.readAsArrayBuffer(file);
          });
          pdfFiles.push({
            id: generateId(),
            name: file.name,
            data: arrayBuffer,
          });
        } catch (error) {
          console.error(`Failed to read ${file.name}:`, error);
          alert(`Failed to read "${file.name}": ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
      }
    }

    setIsProcessing(false);
    if (pdfFiles.length > 0) {
      onFilesAdded(pdfFiles);
    }
  }, [onFilesAdded]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    processFiles(e.dataTransfer.files);
  }, [processFiles]);

  const handleClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      processFiles(e.target.files);
      e.target.value = '';
    }
  }, [processFiles]);

  return (
    <div
      onClick={handleClick}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`
        border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
        transition-colors duration-200
        ${isDragging
          ? 'border-blue-500 bg-blue-50'
          : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
        }
        ${isProcessing ? 'opacity-50 cursor-wait' : ''}
      `}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,application/pdf"
        multiple
        onChange={handleFileChange}
        className="hidden"
      />
      <div className="text-gray-600">
        {isProcessing ? (
          <p>Reading files...</p>
        ) : (
          <>
            <svg
              className="mx-auto h-12 w-12 text-gray-400 mb-3"
              stroke="currentColor"
              fill="none"
              viewBox="0 0 48 48"
            >
              <path
                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <p className="text-sm font-medium">Drop PDF files here or click to upload</p>
            <p className="text-xs text-gray-500 mt-1">Only PDF files are accepted</p>
          </>
        )}
      </div>
    </div>
  );
}
