"use client";

import type { PatientDetail } from "@/lib/api";
import { FieldRow, PatientPill, VitalsStrip, type Vital } from "@/components/aftercare/clinical-ui";
import { Panel } from "@/components/aftercare/clinical-ui";

const VITALS: Vital[] = [
  { label: "Temp", value: "37.1", unit: "°C" },
  { label: "BP", value: "128/84", unit: "mmHg" },
  { label: "HR", value: "76", unit: "bpm" },
  { label: "SpO₂", value: "94", unit: "%", state: "warn" },
  { label: "Resp", value: "18", unit: "/min" },
];

const LABS = [
  { t: "WBC", v: "9.2", u: "K/µL", low: false },
  { t: "Hemoglobin", v: "11.8", u: "g/dL", low: true },
  { t: "Sodium", v: "138", u: "mmol/L", low: false },
  { t: "Creatinine", v: "1.1", u: "mg/dL", low: false },
];

export function OverviewTab({ patient }: { patient: PatientDetail }) {
  const open = patient.alerts.filter((a) => !a.acknowledged).length;
  const ds = patient.discharge_summary;

  return (
    <div className="grid gap-3 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <div className="space-y-3">
        <Panel title="Latest vitals" actions={<span className="text-[11px] text-[#8a97a6]">Today 09:14</span>} bodyClassName="p-3">
          <VitalsStrip vitals={VITALS} />
        </Panel>

        <Panel title="Diagnosis & treatment" bodyClassName="pt-2 pb-2">
          <div className="divide-y divide-[#eef2f5]">
            <FieldRow label="Primary diagnosis">{ds?.diagnosis ?? "-"}</FieldRow>
            <FieldRow label="Procedures">{ds?.procedures ?? "-"}</FieldRow>
            <FieldRow label="Treatment">Antibiotics · oxygen therapy · IV fluids</FieldRow>
            <FieldRow label="Symptoms">Shortness of breath · cough · fatigue</FieldRow>
          </div>
        </Panel>

        <Panel title="Latest labs" bodyClassName="">
          <table className="ac-table">
            <thead>
              <tr>
                <th>Test</th>
                <th className="text-right">Result</th>
                <th className="w-[90px] text-right">Flag</th>
              </tr>
            </thead>
            <tbody>
              {LABS.map((row) => (
                <tr key={row.t}>
                  <td className="font-medium text-slate-900">{row.t}</td>
                  <td className="ac-num text-right">
                    {row.v} <span className="text-[11px] text-[#8a97a6]">{row.u}</span>
                  </td>
                  <td className="text-right">
                    <span className={row.low ? "text-[11px] font-semibold text-[#14509a]" : "text-[11px] font-semibold text-[#0b6b3a]"}>
                      {row.low ? "Low" : "Normal"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>

      <Panel title="Care status" bodyClassName="pt-2 pb-2">
        <div className="divide-y divide-[#eef2f5]">
          <FieldRow label="Stage">
            <PatientPill status={patient.status} />
          </FieldRow>
          <FieldRow label="Follow-up">{patient.followup_jobs?.length ? "Automated calls active" : "Not scheduled"}</FieldRow>
          <FieldRow label="Open alerts">
            <span className={open > 0 ? "text-[#b42318]" : undefined}>{open > 0 ? `${open} to review` : "None"}</span>
          </FieldRow>
          <FieldRow label="Discharged" mono>
            {ds?.discharge_date ?? "-"}
          </FieldRow>
        </div>
        {ds?.instructions && (
          <div className="mt-3 border-t border-[#eef2f5] pt-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[#8a97a6]">Instructions</p>
            <p className="mt-1 line-clamp-6 whitespace-pre-wrap text-[12px] leading-relaxed text-[#3f4a58]">{ds.instructions}</p>
          </div>
        )}
      </Panel>
    </div>
  );
}
