"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2 } from "lucide-react";
import { api, AlertItem } from "@/lib/api";
import { formatEasternDateTime } from "@/lib/datetime";
import { EmptyState, SectionTitle, SeverityPill } from "@/components/aftercare/clinical-ui";
import { severityTone } from "@/lib/clinical-vocab";

function titleCase(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "open" | "ack">("open");

  const fetchAlerts = async () => {
    try {
      setAlerts(await api.getAlerts());
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 5000);
    return () => clearInterval(interval);
  }, []);

  const acknowledge = async (id: string) => {
    try {
      await api.acknowledgeAlert(id);
      fetchAlerts();
    } catch {
      /* ignore */
    }
  };

  const rank: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
  const open = alerts.filter((a) => !a.acknowledged);
  const acked = alerts.filter((a) => a.acknowledged);
  const visible = (
    filter === "open" ? open : filter === "ack" ? acked : alerts
  )
    .slice()
    .sort((a, b) => (rank[a.severity.toLowerCase()] ?? 9) - (rank[b.severity.toLowerCase()] ?? 9));

  return (
    <div className="ac-scroll flex-1 overflow-y-auto px-4 py-4 sm:px-6">
      <div className="mx-auto max-w-[1100px] space-y-3">
        <SectionTitle
          right={
            <>
              <button type="button" onClick={() => setFilter("all")} className={filter === "all" ? "ac-btn ac-btn-primary !h-7 !px-2 !text-[11.5px]" : "ac-btn ac-btn-secondary !h-7 !px-2 !text-[11.5px]"}>
                All {alerts.length}
              </button>
              <button type="button" onClick={() => setFilter("open")} className={filter === "open" ? "ac-btn ac-btn-primary !h-7 !px-2 !text-[11.5px]" : "ac-btn ac-btn-secondary !h-7 !px-2 !text-[11.5px]"}>
                Open {open.length}
              </button>
              <button type="button" onClick={() => setFilter("ack")} className={filter === "ack" ? "ac-btn ac-btn-primary !h-7 !px-2 !text-[11.5px]" : "ac-btn ac-btn-secondary !h-7 !px-2 !text-[11.5px]"}>
                Acknowledged {acked.length}
              </button>
            </>
          }
        >
          Alerts
        </SectionTitle>

        <section className="ac-card overflow-hidden">
          {loading ? (
            <div className="space-y-2 p-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-12 animate-pulse rounded-[5px] bg-[#f4f7f9]" />
              ))}
            </div>
          ) : visible.length === 0 ? (
            <EmptyState title={filter === "open" ? "No open alerts" : "Nothing here"} body="Alerts appear as follow-up calls complete." />
          ) : (
            <ul className="divide-y divide-[#eef2f5]">
              {visible.map((alert) => (
                <li
                  key={alert.id}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-l-[3px] px-3 py-2.5 hover:bg-[#fbfdfc]"
                  style={{ borderLeftColor: alert.acknowledged ? "#e3e8ee" : severityTone(alert.severity).dot }}
                >
                  <SeverityPill severity={alert.severity} />
                  <span className="text-[12px] font-semibold capitalize text-[#3f4a58]">{titleCase(alert.alert_type)}</span>
                  <span className="min-w-0 flex-1 truncate text-[12.5px] text-slate-900">{alert.message}</span>
                  <span className="flex items-center gap-2 text-[11.5px]">
                    {alert.patient_name && (
                      <Link href={`/patients/${alert.patient_id}`} className="font-semibold text-[#0b5d57] hover:underline">
                        {alert.patient_name}
                      </Link>
                    )}
                    <span className="ac-mono text-[10.5px] text-[#a3aeb9]">{formatEasternDateTime(alert.created_at)}</span>
                  </span>
                  {alert.acknowledged ? (
                    <span className="flex items-center gap-1 text-[11px] text-[#0b6b3a]">
                      <CheckCircle2 className="h-3 w-3" /> Done
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => acknowledge(alert.id)}
                      className="ac-btn ac-btn-secondary !h-6 !px-2 !text-[11px]"
                    >
                      Acknowledge
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
