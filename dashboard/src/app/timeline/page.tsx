"use client";

import { useEffect, useMemo, useState } from "react";
import { api, PatientSummary, TimelineEntry } from "@/lib/api";
import { formatEasternDateTime } from "@/lib/datetime";
import { EmptyState, SectionTitle } from "@/components/aftercare/clinical-ui";

export default function TimelinePage() {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [entries, setEntries] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [eventFilter, setEventFilter] = useState("all");

  useEffect(() => {
    api.getPatients().then(setPatients).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedPatientId) {
      setEntries([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const load = async () => {
      try {
        const data = await api.getTimeline(selectedPatientId);
        if (!cancelled) setEntries(data);
      } catch {
        /* ignore */
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    const interval = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [selectedPatientId]);

  const eventTypes = useMemo(() => ["all", ...Array.from(new Set(entries.map((e) => e.event_type)))], [entries]);
  const visible = eventFilter === "all" ? entries : entries.filter((e) => e.event_type === eventFilter);

  return (
    <div className="ac-scroll flex-1 overflow-y-auto px-4 py-4 sm:px-6">
      <div className="mx-auto max-w-[900px] space-y-3">
        <SectionTitle
          right={
            <select
              value={selectedPatientId}
              onChange={(e) => setSelectedPatientId(e.target.value)}
              className="ac-select w-[220px] text-[12.5px]"
              aria-label="Select patient"
            >
              <option value="">Select a patient…</option>
              {patients.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · {p.id}
                </option>
              ))}
            </select>
          }
        >
          Activity
        </SectionTitle>

        {!selectedPatientId ? (
          <section className="ac-card">
            <EmptyState title="Select a patient" body="Choose a patient to see their calls, alerts, and discharge history." />
          </section>
        ) : (
          <>
            <div className="flex items-center justify-between gap-2">
              <span className="text-[12px] text-[#8a97a6]">{entries.length} events</span>
              <div className="ac-seg overflow-x-auto">
                {eventTypes.map((t) => (
                  <button
                    key={t}
                    type="button"
                    data-active={eventFilter === t}
                    onClick={() => setEventFilter(t)}
                    className="ac-seg-item shrink-0 capitalize"
                  >
                    {t === "all" ? "All" : t.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>

            <section className="ac-card overflow-hidden">
              {loading ? (
                <div className="space-y-2 p-3">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="h-10 animate-pulse rounded-[5px] bg-[#f4f7f9]" />
                  ))}
                </div>
              ) : visible.length === 0 ? (
                <EmptyState title="No events" body="Nothing recorded for this view yet." />
              ) : (
                <ul className="divide-y divide-[#eef2f5]">
                  {visible.map((entry) => (
                    <li key={entry.id} className="flex items-baseline gap-3 px-3 py-2">
                      <span className="w-[132px] shrink-0 text-[11px] font-semibold uppercase tracking-[0.04em] text-[#6b7a8a]">
                        {entry.event_type.replace(/_/g, " ")}
                      </span>
                      <span className="min-w-0 flex-1 text-[12.5px] text-[#334155]">{entry.summary}</span>
                      <span className="ac-mono shrink-0 text-[10.5px] text-[#a3aeb9]">
                        {entry.created_at ? formatEasternDateTime(entry.created_at) : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
