"use client";

import type { PatientDetail } from "@/lib/api";
import { Panel } from "@/components/aftercare/clinical-ui";

export function MedicalHistoryTab({ patient }: { patient: PatientDetail }) {
  const ds = patient.discharge_summary;
  return (
    <Panel title="Discharge summary" actions={<span className="ac-mono text-[11px] text-[#8a97a6]">{ds?.discharge_date ?? "-"}</span>}>
      {ds ? (
        <pre className="ac-scroll max-h-[520px] overflow-auto whitespace-pre-wrap bg-[#fbfdfc] p-3 font-mono text-[11.5px] leading-relaxed text-[#3f4a58]">
          {ds.raw_text || "No document text available."}
        </pre>
      ) : (
        <p className="py-6 text-center text-[12.5px] text-[#8a97a6]">No discharge summary on file.</p>
      )}
    </Panel>
  );
}
