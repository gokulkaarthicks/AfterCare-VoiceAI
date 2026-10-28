"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { PatientTableCard } from "@/components/aftercare/patient-management";
import { AppointmentsSidebar } from "@/components/aftercare/appointments-sidebar";
import { api, type PatientSummary } from "@/lib/api";

type LoadState = "loading" | "error" | "ok";

export default function PatientsPage() {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");

  useEffect(() => {
    let cancelled = false;
    api
      .getPatients()
      .then((data) => {
        if (cancelled) return;
        setPatients(data);
        setLoadState("ok");
      })
      .catch(() => {
        if (!cancelled) setLoadState("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const highRisk = patients.filter((p) => p.status === "High Risk" || p.risk_level === "high").length;
  const recovering = patients.filter((p) => p.status === "Recovering").length;

  return (
    <div className="flex min-h-[calc(100vh-88px)] w-full flex-1 flex-col lg:flex-row lg:items-stretch">
      <div className="ac-scroll order-1 min-w-0 flex-1 space-y-3 px-4 py-4 sm:px-6 lg:overflow-y-auto">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[16px] font-semibold tracking-[-0.015em] text-slate-900">Patients</h1>
            <p className="mt-0.5 text-[12px] text-[#6b7a8a]">
              {patients.length} in panel · {recovering} recovering · {highRisk} high risk
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/alerts" className="ac-btn ac-btn-secondary">
              Alerts
            </Link>
            <button type="button" className="ac-btn ac-btn-primary">
              <Plus className="h-3.5 w-3.5" />
              New patient
            </button>
          </div>
        </div>

        <PatientTableCard patients={patients} loadState={loadState} />
      </div>
      <AppointmentsSidebar />
    </div>
  );
}
