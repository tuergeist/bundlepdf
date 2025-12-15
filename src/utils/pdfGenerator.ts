import { PdfFile } from '../types';

const API_URL = import.meta.env.VITE_API_URL || '';

export async function generateMergedPdf(
  editorHtml: string,
  pdfFiles: PdfFile[]
): Promise<{ blob: Blob; failedFiles: string[] }> {
  const formData = new FormData();

  formData.append('content', editorHtml);
  formData.append('file_order', JSON.stringify(pdfFiles.map((f) => f.name)));

  for (const pdfFile of pdfFiles) {
    const blob = new Blob([pdfFile.data], { type: 'application/pdf' });
    formData.append('files', blob, pdfFile.name);
  }

  const response = await fetch(`${API_URL}/api/merge`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to merge PDFs: ${error}`);
  }

  const failedFilesHeader = response.headers.get('X-Failed-Files');
  const failedFiles = failedFilesHeader ? JSON.parse(failedFilesHeader) : [];

  const blob = await response.blob();
  return { blob, failedFiles };
}

export function downloadPdf(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
