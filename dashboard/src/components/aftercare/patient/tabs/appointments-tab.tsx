"use client";

import type { PatientDetail } from "@/lib/api";
import { formatEasternDateTime } from "@/lib/datetime";
import { Panel, StatusPill } from "@/components/aftercare/clinical-ui";
import { appointmentTone } from "@/lib/clinical-vocab";

export function AppointmentsTab({ patient }: { patient: PatientDetail }) {
  if (patient.appointments.length === 0) {
    return (
      <Panel title="Appointments">
        <p className="py-6 text-center text-[12.5px] text-[#8a97a6]">No appointments linked to this chart.</p>
      </Panel>
    );
  }
  return (
    <Panel title="Appointments" bodyClassName="">
      <table className="ac-table">
        <thead>
          <tr>
            <th>Type</th>
            <th>Scheduled</th>
            <th>Notes</th>
            <th className="w-[130px]">Status</th>
          </tr>
        </thead>
        <tbody>
          {patient.appointments.map((ap) => (
            <tr key={ap.id}>
              <td className="capitalize text-slate-900">{ap.appointment_type.replace(/_/g, " ")}</td>
              <td className="ac-num text-[12px]">{ap.scheduled_at ? formatEasternDateTime(ap.scheduled_at) : "TBD"}</td>
              <td className="text-[12px] text-[#5d6b7a]">{ap.notes ?? "-"}</td>
              <td>
                <StatusPill tone={appointmentTone(ap.status)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
