"use client";

import { useState } from "react";
import { FileText, ShieldAlert } from "lucide-react";
import type { PatientDetail } from "@/lib/api";
import { apiInstantToEasternDateKey } from "@/lib/datetime";
import { DischargeUploadModal } from "@/components/aftercare/discharge-upload-modal";
import { Avatar } from "./clinical-ui";

const CARE_TEAM = [
  { name: "Dr. Aris Thorne", role: "Attending", id: "doc-001" },
  { name: "Nadia Bell", role: "Care coordinator", id: "coord-nb" },
  { name: "Marco Silva", role: "Physical therapy", id: "pt-ms" },
];

export function PatientDetailRightRail({
  patient,
  intakeBusy,
  onDischargeFile,
}: {
  patient: PatientDetail;
  intakeBusy: boolean;
  onDischargeFile: (text: string) => Promise<void>;
}) {
  const [modalOpen, setModalOpen] = useState(false);

  const status = patient.status.trim().toLowerCase();
  const blocked = status === "high risk" || status === "discharged";

  const recent = [...patient.appointments]
    .filter((a) => a.notes?.trim() || apiInstantToEasternDateKey(a.scheduled_at))
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))[0];

  return (
    <>
      <aside className="order-2 w-full shrink-0 border-t border-[#e3e8ee] bg-white lg:w-[262px] lg:border-l lg:border-t-0">
        <div className="ac-scroll flex flex-col gap-4 p-4">
          <section>
            <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.07em] text-[#8a97a6]">Contact</h2>
            <dl className="space-y-1 text-[12px]">
              <div className="flex justify-between gap-2">
                <dt className="text-[#6b7a8a]">Phone</dt>
                <dd className="ac-mono text-slate-900">{patient.phone ?? "-"}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-[#6b7a8a]">Email</dt>
                <dd className="truncate text-slate-900">{patient.email ?? "-"}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-[#6b7a8a]">Ward / bed</dt>
                <dd className="truncate text-slate-900">{recent?.notes?.trim() || "-"}</dd>
              </div>
            </dl>
          </section>

          <section>
            <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.07em] text-[#8a97a6]">Care team</h2>
            <ul className="space-y-2">
              {CARE_TEAM.map((m) => (
                <li key={m.id} className="flex items-center gap-2">
                  <Avatar name={m.name} id={m.id} size={24} />
                  <span className="min-w-0">
                    <span className="block truncate text-[12px] font-medium text-slate-900">{m.name}</span>
                    <span className="block truncate text-[11px] text-[#8a97a6]">{m.role}</span>
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.07em] text-[#8a97a6]">Documents</h2>
            {patient.discharge_summary ? (
              <p className="flex items-center gap-2 rounded-[5px] border border-[#e3e8ee] px-2 py-1.5 text-[12px] text-slate-900">
                <FileText className="h-3.5 w-3.5 text-[#0f766e]" />
                <span className="flex-1 truncate">Discharge summary</span>
                <span className="ac-mono text-[10.5px] text-[#a3aeb9]">{patient.discharge_summary.discharge_date ?? "-"}</span>
              </p>
            ) : (
              <p className="text-[12px] text-[#8a97a6]">None on file.</p>
            )}
          </section>

          <section className="border-t border-[#eef2f5] pt-3">
            <button
              type="button"
              disabled={blocked || intakeBusy}
              onClick={() => setModalOpen(true)}
              title={blocked ? "Unavailable for this patient status" : undefined}
              className="ac-btn ac-btn-secondary w-full"
            >
              {blocked ? <ShieldAlert className="h-3.5 w-3.5 text-[#b42318]" /> : <FileText className="h-3.5 w-3.5" />}
              {status === "discharged" ? "Already discharged" : intakeBusy ? "Processing…" : "Upload discharge"}
            </button>
          </section>
        </div>
      </aside>

      <DischargeUploadModal open={modalOpen} onOpenChange={setModalOpen} busy={intakeBusy} onComplete={onDischargeFile} />
    </>
  );
}
