"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { PatientDetail } from "@/lib/api";
import { formatEasternDateTime } from "@/lib/datetime";
import { EmptyState, Panel } from "@/components/aftercare/clinical-ui";

type Interaction = PatientDetail["interactions"][number];

function titleCase(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function CallHistoryTab({ interactions }: { interactions: Interaction[] }) {
  const [openId, setOpenId] = useState<string | null>(interactions[0]?.id ?? null);

  if (interactions.length === 0) {
    return (
      <Panel title="Calls">
        <EmptyState title="No calls recorded" body="Transcripts appear here after a follow-up call completes." />
      </Panel>
    );
  }

  return (
    <Panel title="Calls" actions={<span className="text-[11px] text-[#8a97a6]">{interactions.length} sessions</span>} bodyClassName="">
      <ul className="divide-y divide-[#eef2f5]">
        {interactions.map((inter) => {
          const open = openId === inter.id;
          return (
            <li key={inter.id}>
              <button
                type="button"
                onClick={() => setOpenId(open ? null : inter.id)}
                aria-expanded={open}
                className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-[#fbfdfc]"
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-[12.5px] font-semibold capitalize text-slate-900">
                    {titleCase(inter.interaction_type)} · {inter.channel}
                  </span>
                  <span className="ac-mono block text-[11px] text-[#8a97a6]">{formatEasternDateTime(inter.created_at)}</span>
                </span>
                <span className="text-[11px] text-[#8a97a6]">{inter.responses?.length ?? 0} answers</span>
                <ChevronDown className={open ? "h-3.5 w-3.5 rotate-180 text-[#8a97a6]" : "h-3.5 w-3.5 text-[#8a97a6]"} />
              </button>
              {open && (
                <div className="border-t border-[#eef2f5] bg-[#fbfdfc]">
                  {inter.responses?.length ? (
                    <ul className="divide-y divide-[#f1f5f9]">
                      {inter.responses.map((r, idx) => (
                        <li key={idx} className="px-3 py-2">
                          <p className="text-[11.5px] text-[#6b7a8a]">{r.question_text ?? r.question ?? "Question"}</p>
                          <p className="mt-0.5 text-[12.5px] font-medium text-slate-900">{r.answer}</p>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="px-3 py-3 text-[12px] text-[#8a97a6]">No structured responses stored.</p>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
