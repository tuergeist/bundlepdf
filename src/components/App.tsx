import { useState, useCallback } from 'react';
import { PdfFile } from '../types';
import PdfDropzone from './PdfDropzone';
import PdfList from './PdfList';
import RichTextEditor from './RichTextEditor';
import { generateMergedPdf, downloadPdf } from '../utils/pdfGenerator';

export default function App() {
  const [pdfFiles, setPdfFiles] = useState<PdfFile[]>([]);
  const [editorContent, setEditorContent] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState(false);

  const handleFilesAdded = useCallback((newFiles: PdfFile[]) => {
    setPdfFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const handleReorder = useCallback((reorderedFiles: PdfFile[]) => {
    setPdfFiles(reorderedFiles);
  }, []);

  const handleRemove = useCallback((id: string) => {
    setPdfFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const handleReset = useCallback(() => {
    setPdfFiles([]);
    setEditorContent('');
  }, []);

  const handleGenerate = useCallback(async () => {
    if (pdfFiles.length === 0 && !editorContent.trim()) {
      return;
    }

    setIsGenerating(true);
    try {
      const { blob, failedFiles } = await generateMergedPdf(editorContent, pdfFiles);
      const timestamp = new Date().toISOString().slice(0, 10);
      downloadPdf(blob, `merged-document-${timestamp}.pdf`);

      if (failedFiles.length > 0) {
        alert(`Some files could not be merged:\n\n${failedFiles.join('\n')}`);
      }
    } catch (error) {
      console.error('Failed to generate PDF:', error);
      alert('Failed to generate PDF. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  }, [editorContent, pdfFiles]);

  const canGenerate = pdfFiles.length > 0 || editorContent.replace(/<[^>]*>/g, '').trim().length > 0;

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center gap-3">
            <img src="/logo.svg" alt="BundlePDF Logo" className="h-10 w-10" />
            <div>
              <h1 className="text-2xl font-bold text-gray-900">BundlePDF</h1>
              <p className="text-sm text-gray-600">
                Create a document with a custom front page and merge multiple PDFs
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="space-y-6">
            <section>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">
                Front Page Content
              </h2>
              <RichTextEditor content={editorContent} onChange={setEditorContent} />
              <p className="text-xs text-gray-500 mt-2">
                This content will appear on the first page of your merged document.
              </p>
            </section>
          </div>

          <div className="space-y-6">
            <section>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">
                PDF Documents
              </h2>
              <PdfDropzone onFilesAdded={handleFilesAdded} />
            </section>

            <section>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-semibold text-gray-900">
                  Document Order
                </h2>
                {pdfFiles.length > 0 && (
                  <span className="text-sm text-gray-500">
                    {pdfFiles.length} file{pdfFiles.length !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
              <PdfList
                files={pdfFiles}
                onReorder={handleReorder}
                onRemove={handleRemove}
              />
              {pdfFiles.length > 1 && (
                <p className="text-xs text-gray-500 mt-2">
                  Drag and drop to reorder documents
                </p>
              )}
            </section>
          </div>
        </div>

        <div className="mt-8 flex justify-center gap-4">
          <button
            onClick={handleReset}
            disabled={isGenerating || (!canGenerate)}
            className={`
              px-6 py-3 rounded-lg font-semibold
              transition-all duration-200
              ${!isGenerating && canGenerate
                ? 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }
            `}
          >
            Reset
          </button>
          <button
            onClick={handleGenerate}
            disabled={!canGenerate || isGenerating}
            className={`
              px-8 py-3 rounded-lg font-semibold text-white
              transition-all duration-200
              ${canGenerate && !isGenerating
                ? 'bg-blue-600 hover:bg-blue-700 shadow-lg hover:shadow-xl'
                : 'bg-gray-400 cursor-not-allowed'
              }
            `}
          >
            {isGenerating ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Generating...
              </span>
            ) : (
              'Generate & Download PDF'
            )}
          </button>
        </div>

        {!canGenerate && (
          <p className="text-center text-sm text-gray-500 mt-4">
            Add some content or upload PDFs to generate a document
          </p>
        )}
      </main>

      <footer className="mt-auto py-6 text-center text-sm text-gray-500">
        Your uploaded PDFs are removed from the server when you click Reset.
      </footer>
    </div>
  );
}
