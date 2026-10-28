"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowUpRight, Search } from "lucide-react";
import type { PatientSummary } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Avatar, EmptyState, PatientPill } from "./clinical-ui";

const FILTERS = ["All", "Recovering", "High Risk", "Stable", "Discharged"] as const;

export function PatientTableCard({
  patients,
  loadState,
  highlightPatientId,
}: {
  patients: PatientSummary[];
  loadState: "loading" | "error" | "ok";
  highlightPatientId?: string;
}) {
  const [filter, setFilter] = useState<string>("All");
  const [query, setQuery] = useState("");

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return patients.filter((p) => {
      const matchesStatus = filter === "All" || p.status === filter;
      const matchesQuery =
        !q || p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q) || (p.reason ?? "").toLowerCase().includes(q);
      return matchesStatus && matchesQuery;
    });
  }, [patients, filter, query]);

  return (
    <section className="ac-card overflow-hidden">
      <div className="flex flex-col gap-2 border-b border-[#e3e8ee] p-2.5 sm:flex-row sm:items-center sm:justify-between">
        <div className="ac-seg overflow-x-auto">
          {FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              data-active={filter === f}
              onClick={() => setFilter(f)}
              className="ac-seg-item shrink-0"
            >
              {f}
            </button>
          ))}
        </div>
        <div className="relative sm:w-[240px]">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#8a97a6]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name or MRN"
            className="ac-input !h-[30px] pl-8 text-[12.5px]"
            aria-label="Search patients"
          />
        </div>
      </div>

      {loadState === "error" ? (
        <EmptyState title="Unable to load patients" body="The chart service is unreachable. Check the backend and reload." />
      ) : loadState === "loading" ? (
        <div className="space-y-2 p-3">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-11 animate-pulse rounded-[5px] bg-[#f4f7f9]" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <EmptyState title="No patients match" body="Try a different status or clear the search." />
      ) : (
        <div className="ac-scroll overflow-x-auto">
          <table className="ac-table min-w-[760px]">
            <thead>
              <tr>
                <th className="w-[110px]">MRN</th>
                <th>Patient</th>
                <th>Reason for visit</th>
                <th className="w-[130px]">Status</th>
                <th className="w-[76px] text-right">Chart</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((p) => (
                <tr
                  key={p.id}
                  data-selected={highlightPatientId === p.id ? "true" : undefined}
                  data-alert={p.risk_level === "high" ? "true" : undefined}
                >
                  <td>
                    <span className="ac-mono text-[11.5px] text-[#5d6b7a]">{p.id}</span>
                  </td>
                  <td>
                    <Link href={`/patients/${p.id}`} className="group flex items-center gap-2.5">
                      <Avatar name={p.name} id={p.id} />
                      <span className="min-w-0">
                        <span className="block truncate text-[12.5px] font-semibold text-slate-900 group-hover:text-[#0b5d57] group-hover:underline">
                          {p.name}
                        </span>
                        {p.age != null && <span className="text-[11px] text-[#8a97a6]">{p.age} y</span>}
                      </span>
                    </Link>
                  </td>
                  <td className="max-w-[340px]">
                    <span className="line-clamp-1 text-[12.5px] text-[#3f4a58]">{p.reason ?? "-"}</span>
                  </td>
                  <td>
                    <PatientPill status={p.status} />
                  </td>
                  <td className="text-right">
                    <Link href={`/patients/${p.id}`} className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#0b5d57] hover:underline">
                      Open
                      <ArrowUpRight className="h-3 w-3" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between border-t border-[#eef2f5] px-3 py-1.5 text-[11px] text-[#8a97a6]">
        <span>
          {visible.length} of {patients.length} patients
        </span>
        <span className="hidden sm:block">US Eastern</span>
      </div>
    </section>
  );
}

export { cn };
