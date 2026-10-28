"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Download, FileText, Trash2, UploadCloud, X } from "lucide-react";
import { formatEasternFromEpochMs } from "@/lib/datetime";
import { extractTextFromPdf } from "@/lib/pdf-text";
import { cn } from "@/lib/cn";

const ACCEPT = ".txt,.text,.md,.markdown,.pdf,application/pdf";
const ACCEPT_LABEL = "PDF, TXT, or Markdown";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  busy: boolean;
  onComplete: (text: string) => Promise<void>;
};

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function fileKind(file: File): "pdf" | "txt" {
  const name = file.name.toLowerCase();
  if (name.endsWith(".pdf") || file.type === "application/pdf") return "pdf";
  return "txt";
}

/** Normalize an uploaded discharge file to plain text for Triage Agent POST /intake. */
async function fileToDischargeText(file: File): Promise<string> {
  const name = file.name.toLowerCase();
  const ext = name.split(".").pop() ?? "";

  if (ext === "pdf" || file.type === "application/pdf") {
    try {
      const t = await extractTextFromPdf(file);
      if (!t.trim()) {
        throw new Error(
          "No readable text found in this PDF. Scanned/image-only PDFs are not supported: use a text PDF or a .txt file.",
        );
      }
      return t;
    } catch (e) {
      if (e instanceof Error && e.message.startsWith("No readable text")) throw e;
      throw new Error(
        e instanceof Error
          ? `Could not read PDF: ${e.message}`
          : "Could not read PDF. Try a .txt discharge note instead.",
      );
    }
  }

  if (["txt", "md", "markdown", "text"].includes(ext) || file.type === "text/plain" || file.type === "text/markdown") {
    const t = await file.text();
    if (!t.trim()) throw new Error("File is empty.");
    return t;
  }

  throw new Error("Supported formats: PDF, TXT, or Markdown. Word documents are not supported.");
}

export function DischargeUploadModal({ open, onOpenChange, busy, onComplete }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleOpenChange = (next: boolean) => {
    setFile(null);
    setError(null);
    setDragOver(false);
    onOpenChange(next);
  };

  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onOpenChange(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onOpenChange]);

  const pick = () => inputRef.current?.click();

  const onFile = useCallback((f: File | undefined) => {
    if (!f) return;
    setError(null);
    setFile(f);
  }, []);

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFile(e.target.files?.[0]);
    e.target.value = "";
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };

  const handleComplete = async () => {
    if (!file || busy) return;
    setError(null);
    try {
      const text = await fileToDischargeText(file);
      await onComplete(text);
      handleOpenChange(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    }
  };

  if (!open) return null;

  const dateStr = file ? formatEasternFromEpochMs(file.lastModified) : "";

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy) handleOpenChange(false);
      }}
    >
      <div className="absolute inset-0 bg-[#0f172a]/45" aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="discharge-modal-title"
        className="ac-enter relative z-[101] flex max-h-[min(92vh,720px)] w-full max-w-[560px] flex-col overflow-hidden rounded-[10px] border border-[#e3e8ee] bg-white shadow-[0_18px_48px_rgb(15_23_42/0.28)]"
      >
        <div className="flex items-start justify-between border-b border-[#e3e8ee] px-5 py-3.5">
          <div>
            <h2 id="discharge-modal-title" className="text-[15px] font-semibold text-slate-900">
              Upload discharge report
            </h2>
            <p className="mt-0.5 text-[11.5px] text-[#8a97a6]">
              Parsed into diagnosis, medications, and a follow-up questionnaire.
            </p>
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => handleOpenChange(false)}
            className="rounded-[5px] p-1 text-[#8a97a6] transition-colors hover:bg-[#f1f5f9] hover:text-slate-900 disabled:opacity-50"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

          <div
            ref={bodyRef}
            className="ac-scroll min-h-0 flex-1 overflow-y-auto px-5 py-4"
          >
          <input ref={inputRef} type="file" accept={ACCEPT} className="hidden" onChange={onInputChange} />

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            className={cn(
              "flex min-h-[180px] flex-col items-center justify-center rounded-[8px] border border-dashed px-4 py-8 transition-colors",
              dragOver ? "border-[#0f766e] bg-[#f1f8f7]" : "border-[#cfd8e1] bg-[#fbfdfc]",
            )}
          >
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[#e6f4f2]">
              <UploadCloud className="h-5 w-5 text-[#0f766e]" strokeWidth={1.8} />
            </div>
            <p className="text-center text-[12.5px] text-[#5d6b7a]">
              Drag a file here, or{" "}
              <button
                type="button"
                onClick={pick}
                className="font-semibold text-[#0b5d57] underline underline-offset-2 hover:text-[#0f766e]"
              >
                browse
              </button>{" "}
              to upload
            </p>
            <p className="mt-1.5 text-center text-[11px] text-[#94a3a2]">Accepted: {ACCEPT_LABEL} · max ~10 MB</p>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-[#eef2f5] pb-3">
            <span className="text-[11px] text-[#8a97a6]">Need a template?</span>
            <a
              href="/discharge-sample-format.txt"
              download="discharge-sample-format.txt"
              className="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-[#0b5d57] hover:underline"
            >
              <Download className="h-3 w-3" />
              Sample .txt
            </a>
            <a
              href="/discharge-sample-format.pdf"
              download="discharge-sample-format.pdf"
              className="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-[#0b5d57] hover:underline"
            >
              <Download className="h-3 w-3" />
              Sample .pdf
            </a>
          </div>

          {error && (
            <p className="mt-3 rounded-[5px] border border-[#f5c2bb] bg-[#fef3f2] px-2.5 py-1.5 text-[12px] text-[#b42318]">
              {error}
            </p>
          )}

          {file && (
            <div className="mt-3 flex items-start gap-3 rounded-[7px] border border-[#e3e8ee] bg-white p-2.5 shadow-[0_1px_2px_rgb(15_23_42/0.05)]">
              <div className="flex h-9 w-8 shrink-0 items-center justify-center rounded-[4px] border border-[#f3c6c0] bg-[#fdecea] text-[9px] font-bold text-[#b42318]">
                {fileKind(file) === "pdf" ? "PDF" : "TXT"}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[12.5px] font-semibold text-slate-900">{file.name}</p>
                <p className="ac-mono mt-0.5 text-[10.5px] text-[#8a97a6]">
                  {dateStr} · {formatBytes(file.size)}
                </p>
                <p className="mt-1 inline-flex items-center gap-1 text-[10.5px] font-medium text-[#0b6b3a]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#12a150]" /> Ready to upload
                </p>
              </div>
              <button
                type="button"
                disabled={busy}
                onClick={() => setFile(null)}
                className="shrink-0 rounded-[5px] p-1.5 text-[#8a97a6] hover:bg-[#f1f5f9] hover:text-[#b42318] disabled:opacity-50"
                aria-label="Remove file"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          <p className="mt-3 flex items-start gap-1.5 text-[10.5px] leading-snug text-[#a3aeb9]">
            <FileText className="mt-px h-3 w-3 shrink-0" />
            Processing creates or updates this patient&apos;s chart, classifies risk, and schedules the automated
            follow-up call.
          </p>
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-[#e3e8ee] bg-[#fbfdfc] px-5 py-3 sm:flex-row sm:justify-end">
          <button type="button" disabled={busy} onClick={() => handleOpenChange(false)} className="ac-btn ac-btn-secondary">
            Cancel
          </button>
          <button type="button" disabled={!file || busy} onClick={handleComplete} className="ac-btn ac-btn-primary">
            <UploadCloud className="h-3.5 w-3.5" />
            {busy ? "Processing…" : "Upload & process"}
          </button>
        </div>
      </div>
    </div>
  );
}
