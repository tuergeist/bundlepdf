export interface PdfFile {
  id: string;
  name: string;
  data: ArrayBuffer;
  pageCount?: number;
}
