/**
 * Client-side PDF text extraction via PDF.js.
 *
 * Worker is served from /pdf.worker.min.mjs (copied from pdfjs-dist into public/).
 * Image-only or scanned PDFs yield an empty string (no text layer).
 */
import { getDocument, GlobalWorkerOptions } from "pdfjs-dist";

let workerReady = false;

function ensureWorker() {
  if (workerReady) return;
  GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
  workerReady = true;
}

/** Extract plain text from a PDF File for Triage Agent intake. */
export async function extractTextFromPdf(file: File): Promise<string> {
  ensureWorker();
  const data = new Uint8Array(await file.arrayBuffer());
  const loadingTask = getDocument({ data });
  const doc = await loadingTask.promise;
  const pages: string[] = [];

  try {
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i);
      const content = await page.getTextContent();
      const line = content.items
        .map((item) => ("str" in item ? String(item.str) : ""))
        .join(" ")
        .replace(/\s+/g, " ")
        .trim();
      if (line) pages.push(line);
      page.cleanup();
    }
  } finally {
    // PDF.js v6+: PDFDocumentProxy exposes cleanup(); destroy() is on the loading task.
    await doc.cleanup();
    await loadingTask.destroy();
  }

  return pages.join("\n\n").trim();
}
