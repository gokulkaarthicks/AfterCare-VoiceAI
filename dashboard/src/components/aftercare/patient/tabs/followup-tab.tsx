"use client";

import type { PatientDetail } from "@/lib/api";
import { formatEasternDateTime } from "@/lib/datetime";
import { Panel, StatusPill } from "@/components/aftercare/clinical-ui";
import { followupTone } from "@/lib/clinical-vocab";

function titleCase(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function FollowupTab({ patient, onSchedule }: { patient: PatientDetail; onSchedule: () => void }) {
  const jobs = patient.followup_jobs ?? [];
  return (
    <div className="space-y-3">
      <Panel
        title="Follow-up calls"
        actions={
          <button type="button" onClick={onSchedule} className="ac-btn ac-btn-primary !h-7 !px-2.5 !text-[11.5px]">
            Schedule
          </button>
        }
        bodyClassName=""
      >
        {jobs.length === 0 ? (
          <p className="py-6 text-center text-[12.5px] text-[#8a97a6]">No follow-up calls scheduled.</p>
        ) : (
          <table className="ac-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Scheduled</th>
                <th className="w-[130px]">Status</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td className="font-medium capitalize text-slate-900">{titleCase(job.job_type)}</td>
                  <td className="ac-num text-[12px]">{job.scheduled_at ? formatEasternDateTime(job.scheduled_at) : "-"}</td>
                  <td>
                    <StatusPill tone={followupTone(job.status)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <Panel title="Questionnaire" actions={patient.questionnaire && <span className="text-[11px] text-[#8a97a6]">{patient.questionnaire.questions.length} questions</span>}>
        {patient.questionnaire ? (
          <>
            <p className="mb-2 text-[12px] text-[#6b7a8a]">{patient.questionnaire.diagnosis_context}</p>
            <ol className="divide-y divide-[#eef2f5]">
              {patient.questionnaire.questions.map((q, idx) => (
                <li key={q.id} className="flex gap-2.5 py-2">
                  <span className="ac-num text-[11.5px] font-semibold text-[#8a97a6]">{idx + 1}.</span>
                  <span className="min-w-0 flex-1 text-[12.5px] leading-snug text-slate-900">{q.text}</span>
                  <span className="ac-mono shrink-0 text-[10.5px] text-[#a3aeb9]">{q.question_type}</span>
                </li>
              ))}
            </ol>
          </>
        ) : (
          <p className="py-6 text-center text-[12.5px] text-[#8a97a6]">Generated after intake completes.</p>
        )}
      </Panel>
    </div>
  );
}
