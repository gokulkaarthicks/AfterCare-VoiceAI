"use client";

import type { PatientDetail } from "@/lib/api";
import { formatEasternDateTime } from "@/lib/datetime";
import { EmptyState, Panel, SeverityPill } from "@/components/aftercare/clinical-ui";
import { severityTone } from "@/lib/clinical-vocab";

type PatientAlert = PatientDetail["alerts"][number];

function titleCase(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Split a stored alert message into its prose, assessment, and flag list. */
function parseAlertMessage(message: string) {
  const raw = (message || "").trim();
  const flagsMatch = raw.match(/\bFlags:\s*(.+)$/i);
  const flags = flagsMatch?.[1]?.split(/[;,]/).map((f) => f.trim()).filter(Boolean) ?? [];
  const withoutFlags = raw.replace(/\bFlags:\s*.+$/i, "").trim();
  const assessment = withoutFlags.match(/\bAssessment:\s*(.+)$/i)?.[1]?.trim() ?? "";
  return { flags, assessment, text: withoutFlags.replace(/\bAssessment:\s*.+$/i, "").trim() };
}

export function AlertsTab({ alerts }: { alerts: PatientAlert[] }) {
  if (alerts.length === 0) {
    return (
      <Panel title="Alerts">
        <EmptyState title="No alerts" body="Nothing has been flagged for this patient." />
      </Panel>
    );
  }

  return (
    <Panel title="Alerts" bodyClassName="">
      <ul className="divide-y divide-[#eef2f5]">
        {alerts.map((a) => {
          const parsed = parseAlertMessage(a.message);
          return (
            <li
              key={a.id}
              className="border-l-[3px] px-3 py-2.5"
              style={{ borderLeftColor: a.acknowledged ? "#d8dee5" : severityTone(a.severity).dot }}
            >
              <div className="flex flex-wrap items-center gap-2">
                <SeverityPill severity={a.severity} />
                <span className="text-[12.5px] font-semibold capitalize text-slate-900">{titleCase(a.alert_type)}</span>
                <span className="ac-mono ml-auto text-[10.5px] text-[#a3aeb9]">{formatEasternDateTime(a.created_at)}</span>
                <span className={a.acknowledged ? "text-[11px] text-[#8a97a6]" : "text-[11px] font-semibold text-[#b42318]"}>
                  {a.acknowledged ? "Acknowledged" : "Open"}
                </span>
              </div>
              <p className="mt-1 text-[12.5px] leading-snug text-[#3f4a58]">{parsed.text || a.message}</p>
              {parsed.assessment && (
                <p className="mt-1 text-[12px] leading-snug text-[#8a5106]">{parsed.assessment}</p>
              )}
              {parsed.flags.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {parsed.flags.map((f, i) => (
                    <span key={i} className="rounded-[3px] bg-[#fff5f4] px-1.5 py-[1px] text-[10.5px] font-medium text-[#a33a3a]">
                      {f}
                    </span>
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
