"use client";

import { CalendarPlus } from "lucide-react";
import type { PatientDetail } from "@/lib/api";
import { Avatar, PatientPill, StatusPill } from "./clinical-ui";
import { riskTone } from "@/lib/clinical-vocab";

export function ChartBanner({ patient, ageLabel, onScheduleFollowup }: { patient: PatientDetail; ageLabel: string; onScheduleFollowup: () => void }) {
  const risk = riskTone(patient.risk_level);
  const diagnosis = patient.discharge_summary?.diagnosis ?? "-";

  return (
    <section className="flex flex-col gap-3 border-b border-[#e3e8ee] bg-white px-4 py-3.5 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex min-w-0 items-center gap-3">
        <Avatar name={patient.name} id={patient.id} size={40} />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[17px] font-semibold leading-tight tracking-[-0.015em] text-slate-900">{patient.name}</h1>
            <PatientPill status={patient.status} />
            {risk && patient.status !== "High Risk" && <StatusPill tone={risk} />}
          </div>
          <p className="mt-1 truncate text-[12px] text-[#6b7a8a]">
            <span className="ac-mono">{patient.id}</span>
            <span className="px-1.5 text-[#cbd5e1]">·</span>
            {ageLabel}
            {patient.dob && (
              <>
                <span className="px-1.5 text-[#cbd5e1]">·</span>
                DOB <span className="ac-mono">{patient.dob.slice(0, 10)}</span>
              </>
            )}
            <span className="px-1.5 text-[#cbd5e1]">·</span>
            {diagnosis}
          </p>
        </div>
      </div>

      <button type="button" onClick={onScheduleFollowup} className="ac-btn ac-btn-primary shrink-0">
        <CalendarPlus className="h-3.5 w-3.5" />
        Schedule follow-up
      </button>
    </section>
  );
}
