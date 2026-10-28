"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { CalendarPlus, Search } from "lucide-react";
import { api, AppointmentItem } from "@/lib/api";
import { formatEasternDateTime } from "@/lib/datetime";
import { useDoctor } from "@/lib/doctor-context";
import { Avatar, EmptyState, SectionTitle, StatusPill } from "@/components/aftercare/clinical-ui";
import { appointmentTone } from "@/lib/clinical-vocab";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "pending_manual", label: "Needs scheduling" },
  { id: "pending_confirmation", label: "Awaiting confirmation" },
  { id: "confirmed", label: "Confirmed" },
  { id: "completed", label: "Completed" },
  { id: "cancelled", label: "Cancelled" },
];

function titleCase(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function AppointmentsPage() {
  const [appointments, setAppointments] = useState<AppointmentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const { doctor } = useDoctor();

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await api.getAppointments(doctor?.id);
        if (!cancelled) setAppointments(data);
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
  }, [doctor?.id]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: appointments.length };
    for (const a of appointments) c[a.status] = (c[a.status] ?? 0) + 1;
    return c;
  }, [appointments]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return appointments.filter((a) => {
      if (filter !== "all" && a.status !== filter) return false;
      if (!q) return true;
      return (
        (a.patient_name ?? "").toLowerCase().includes(q) ||
        a.appointment_type.replace(/_/g, " ").toLowerCase().includes(q) ||
        (a.doctor_name ?? "").toLowerCase().includes(q) ||
        a.patient_id.includes(q)
      );
    });
  }, [appointments, filter, query]);

  return (
    <div className="ac-scroll flex-1 overflow-y-auto px-4 py-4 sm:px-6">
      <div className="mx-auto max-w-[1100px] space-y-3">
        <SectionTitle
          right={
            <button type="button" className="ac-btn ac-btn-primary">
              <CalendarPlus className="h-3.5 w-3.5" />
              New appointment
            </button>
          }
        >
          Schedule
        </SectionTitle>

        <div className="ac-card flex flex-col gap-2 p-2.5 lg:flex-row lg:items-center lg:justify-between">
          <div className="ac-seg overflow-x-auto">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                data-active={filter === f.id}
                onClick={() => setFilter(f.id)}
                className="ac-seg-item shrink-0"
              >
                {f.label}
                <span className="ac-num text-[10px] text-[#a3aeb9]">{counts[f.id] ?? 0}</span>
              </button>
            ))}
          </div>
          <div className="relative lg:w-[240px]">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#8a97a6]" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search patient or provider"
              className="ac-input !h-[30px] pl-8 text-[12.5px]"
              aria-label="Search appointments"
            />
          </div>
        </div>

        <section className="ac-card overflow-hidden">
          {loading ? (
            <div className="space-y-2 p-3">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="h-12 animate-pulse rounded-[5px] bg-[#f4f7f9]" />
              ))}
            </div>
          ) : visible.length === 0 ? (
            <EmptyState
              title={appointments.length === 0 ? "No appointments" : "Nothing matches"}
              body={appointments.length === 0 ? "Appointments created by the follow-up pipeline appear here." : "Try another filter."}
            />
          ) : (
            <table className="ac-table min-w-[720px]">
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>Visit</th>
                  <th>Scheduled</th>
                  <th>Provider</th>
                  <th className="w-[140px]">Status</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((ap) => (
                  <tr key={ap.id} data-alert={ap.status === "pending_manual" ? "true" : undefined}>
                    <td>
                      {ap.patient_name ? (
                        <Link href={`/patients/${ap.patient_id}`} className="flex items-center gap-2 font-semibold text-slate-900 hover:text-[#0b5d57] hover:underline">
                          <Avatar name={ap.patient_name} id={ap.patient_id} size={24} />
                          <span className="truncate">{ap.patient_name}</span>
                        </Link>
                      ) : (
                        <span className="text-[#8a97a6]">Unassigned</span>
                      )}
                    </td>
                    <td className="capitalize">{titleCase(ap.appointment_type)}</td>
                    <td className="ac-num text-[12px]">
                      {ap.scheduled_at ? formatEasternDateTime(ap.scheduled_at) : "TBD"}
                    </td>
                    <td className="text-[12px] text-[#5d6b7a]">{ap.doctor_name ?? "-"}</td>
                    <td>
                      <StatusPill tone={appointmentTone(ap.status)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  );
}
