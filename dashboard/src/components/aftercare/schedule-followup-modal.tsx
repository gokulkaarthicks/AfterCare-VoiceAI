"use client";

import { useEffect, useMemo, useState } from "react";
import { CalendarDays, Clock, CalendarPlus, X, Info } from "lucide-react";
import { api } from "@/lib/api";
import { defaultEasternDateTimeParts, DISPLAY_TIME_ZONE } from "@/lib/datetime";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  patientId: string;
  onScheduled: () => Promise<void>;
};

const MINUTE_OPTIONS = Array.from({ length: 60 }, (_, i) => String(i).padStart(2, "0"));

function from24Hour(time24: string): { h12: number; m: string; ap: "AM" | "PM" } {
  const [H, rawM] = time24.split(":");
  const Hn = parseInt(H ?? "0", 10);
  let Mn = parseInt(rawM ?? "0", 10);
  if (Number.isNaN(Mn)) Mn = 0;
  Mn = Math.max(0, Math.min(59, Mn));
  const M = String(Mn).padStart(2, "0");
  const ap: "AM" | "PM" = Hn >= 12 ? "PM" : "AM";
  let h12 = Hn % 12;
  if (h12 === 0) h12 = 12;
  return { h12, m: M, ap };
}

function to24Hour(h12: number, minute: string, ap: "AM" | "PM"): string {
  let H: number;
  if (ap === "AM") {
    H = h12 === 12 ? 0 : h12;
  } else {
    H = h12 === 12 ? 12 : h12 + 12;
  }
  return `${String(H).padStart(2, "0")}:${minute}`;
}

/** DB/async pipeline can lag the HTTP response: refetch a few times so the list updates. */
async function refreshAfterSchedule(onScheduled: () => Promise<void>): Promise<void> {
  await onScheduled();
  await new Promise((r) => setTimeout(r, 450));
  await onScheduled();
  await new Promise((r) => setTimeout(r, 900));
  await onScheduled();
}

const fieldLabel = "mb-1 block text-[11px] font-semibold text-[#3f4a58]";

export function ScheduleFollowupModal({ open, onOpenChange, patientId, onScheduled }: Props) {
  const [date, setDate] = useState("");
  const [h12, setH12] = useState(10);
  const [minute, setMinute] = useState("00");
  const [ap, setAp] = useState<"AM" | "PM">("AM");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setError(null);
      return;
    }
    const d = defaultEasternDateTimeParts();
    setDate(d.date);
    const t = from24Hour(d.time);
    setH12(t.h12);
    setMinute(t.m);
    setAp(t.ap);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onOpenChange(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onOpenChange]);

  const datePreview = useMemo(() => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
    const [y, mo, d] = date.split("-").map(Number);
    const dt = new Date(y, mo - 1, d);
    if (Number.isNaN(dt.getTime())) return null;
    return dt.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
  }, [date]);

  const timePreview = useMemo(() => {
    const hour = ap === "AM" ? (h12 === 12 ? 0 : h12) : h12 === 12 ? 12 : h12 + 12;
    const d = new Date(2026, 0, 1, hour, parseInt(minute, 10));
    return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  }, [h12, minute, ap]);

  const time24 = to24Hour(h12, minute, ap);

  const handleSubmit = async () => {
    if (!date.trim()) {
      setError("Choose a date.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.scheduleDoctorFollowup(patientId, { eastern_date: date.trim(), eastern_time: time24 });
      await refreshAfterSchedule(onScheduled);
      onOpenChange(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not schedule follow-up.");
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy) onOpenChange(false);
      }}
    >
      <div className="absolute inset-0 bg-[#0f172a]/45" aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="schedule-followup-title"
        className="ac-enter relative z-[101] w-full max-w-[520px] overflow-hidden rounded-[10px] border border-[#e3e8ee] bg-white shadow-[0_18px_48px_rgb(15_23_42/0.28)]"
      >
        <div className="flex items-start justify-between border-b border-[#e3e8ee] px-5 py-3.5">
          <div>
            <h2 id="schedule-followup-title" className="text-[15px] font-semibold text-slate-900">
              Schedule follow-up call
            </h2>
            <p className="mt-0.5 text-[11.5px] text-[#8a97a6]">
              Automated voice check-in · {DISPLAY_TIME_ZONE}
            </p>
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => onOpenChange(false)}
            className="rounded-[5px] p-1 text-[#8a97a6] transition-colors hover:bg-[#f1f5f9] hover:text-slate-900 disabled:opacity-50"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 px-5 py-4">
          <div className="flex gap-2 rounded-[6px] border border-[#dcebe7] bg-[#f5fbf9] px-3 py-2 text-[11.5px] leading-snug text-[#3f6b5f]">
            <Info className="mt-px h-3.5 w-3.5 shrink-0 text-[#0f766e]" />
            <p>
              The scheduler dials the patient at this exact moment. Times are{" "}
              <span className="font-semibold">US Eastern</span>: convert from your local zone if needed.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className={fieldLabel}>
                <span className="inline-flex items-center gap-1">
                  <CalendarDays className="h-3 w-3 text-[#94a3a2]" /> Date
                </span>
              </span>
              <input
                id="sf-date"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                disabled={busy}
                className="ac-input [color-scheme:light]"
              />
              <span className="mt-1 block h-4 truncate text-[10.5px] text-[#8a97a6]">{datePreview ?? ""}</span>
            </label>

            <div>
              <span className={fieldLabel}>
                <span className="inline-flex items-center gap-1">
                  <Clock className="h-3 w-3 text-[#94a3a2]" /> Time (Eastern)
                </span>
              </span>
              <div className="grid grid-cols-[1fr_1fr_0.85fr] gap-1.5">
                <select
                  id="sf-hour"
                  value={h12}
                  onChange={(e) => setH12(parseInt(e.target.value, 10))}
                  disabled={busy}
                  aria-label="Hour"
                  className="ac-select w-full"
                >
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </select>
                <select
                  id="sf-min"
                  value={minute}
                  onChange={(e) => setMinute(e.target.value)}
                  disabled={busy}
                  aria-label="Minute"
                  className="ac-select ac-num w-full"
                >
                  {MINUTE_OPTIONS.map((m) => (
                    <option key={m} value={m}>
                      :{m}
                    </option>
                  ))}
                </select>
                <select
                  id="sf-ap"
                  value={ap}
                  onChange={(e) => setAp(e.target.value as "AM" | "PM")}
                  disabled={busy}
                  aria-label="AM or PM"
                  className="ac-select w-full"
                >
                  <option value="AM">AM</option>
                  <option value="PM">PM</option>
                </select>
              </div>
              <span className="mt-1 block h-4 text-[10.5px] text-[#8a97a6]">
                {timePreview} · <span className="ac-mono">{time24}</span>
              </span>
            </div>
          </div>

          {error && (
            <p className="rounded-[5px] border border-[#f5c2bb] bg-[#fef3f2] px-2.5 py-1.5 text-[12px] text-[#b42318]">
              {error}
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[#e3e8ee] bg-[#fbfdfc] px-5 py-3">
          <button type="button" disabled={busy} onClick={() => onOpenChange(false)} className="ac-btn ac-btn-secondary">
            Cancel
          </button>
          <button type="button" disabled={busy} onClick={() => void handleSubmit()} className="ac-btn ac-btn-primary">
            <CalendarPlus className="h-3.5 w-3.5" />
            {busy ? "Scheduling…" : "Schedule call"}
          </button>
        </div>
      </div>
    </div>
  );
}
