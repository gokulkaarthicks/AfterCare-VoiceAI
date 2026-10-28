"use client";

import type { PatientDetail } from "@/lib/api";
import { Panel } from "@/components/aftercare/clinical-ui";

export function MedicationsTab({ patient }: { patient: PatientDetail }) {
  if (patient.medications.length === 0) {
    return (
      <Panel title="Medications">
        <p className="py-6 text-center text-[12.5px] text-[#8a97a6]">No medications on file.</p>
      </Panel>
    );
  }
  return (
    <Panel title="Medications" actions={<span className="text-[11px] text-[#8a97a6]">{patient.medications.length} active</span>} bodyClassName="">
      <table className="ac-table">
        <thead>
          <tr>
            <th>Medication</th>
            <th>Dose</th>
            <th>Frequency</th>
            <th className="w-[80px]">Status</th>
          </tr>
        </thead>
        <tbody>
          {patient.medications.map((m) => (
            <tr key={m.id}>
              <td className="font-medium text-slate-900">{m.name}</td>
              <td className="ac-mono text-[11.5px]">{m.dosage}</td>
              <td className="ac-mono text-[11.5px] text-[#5d6b7a]">{m.frequency}</td>
              <td>
                <span className="text-[11px] font-semibold text-[#0b6b3a]">Active</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
