"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api, PatientDetail } from "@/lib/api";
import { ageFromIsoDob } from "@/lib/patient";
import { cn } from "@/lib/cn";
import { PatientDetailRightRail } from "@/components/aftercare/patient-detail-right-rail";
import { ScheduleFollowupModal } from "@/components/aftercare/schedule-followup-modal";
import { ChartBanner } from "@/components/aftercare/chart-header";
import { EmptyState } from "@/components/aftercare/clinical-ui";
import {
  AlertsTab,
  AppointmentsTab,
  CallHistoryTab,
  FollowupTab,
  MedicationsTab,
  MedicalHistoryTab,
  OverviewTab,
} from "@/components/aftercare/patient/tabs";

const TABS = [
  { id: "overview", label: "Summary" },
  { id: "medical", label: "History" },
  { id: "medications", label: "Medications" },
  { id: "followup", label: "Follow-up" },
  { id: "appointments", label: "Appointments" },
  { id: "ai-calls", label: "Calls" },
  { id: "alerts", label: "Alerts" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function PatientDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [apiPatient, setApiPatient] = useState<PatientDetail | null>(null);
  const [apiAttempted, setApiAttempted] = useState(false);
  const [intakeBusy, setIntakeBusy] = useState(false);
  const [scheduleFollowupOpen, setScheduleFollowupOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  const patient = apiPatient;

  const fetchPatient = useCallback(async () => {
    try {
      const data = await api.getPatient(id);
      setApiPatient(data);
    } catch {
      setApiPatient(null);
    } finally {
      setApiAttempted(true);
    }
  }, [id]);

  useEffect(() => {
    setApiAttempted(false);
    setApiPatient(null);
    fetchPatient();
    const t = setInterval(fetchPatient, 4000);
    return () => clearInterval(t);
  }, [fetchPatient]);

  useEffect(() => {
    const onVis = () => {
      if (document.visibilityState === "visible") void fetchPatient();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [fetchPatient]);

  const voiceInteractions = useMemo(() => {
    if (!patient) return [];
    return patient.interactions.filter((i) => {
      const ch = (i.channel || "").toLowerCase();
      const ty = (i.interaction_type || "").toLowerCase();
      return ch === "voice" || ty.includes("voice");
    });
  }, [patient]);

  const handleDischargeFile = async (text: string) => {
    if (!patient) return;
    setIntakeBusy(true);
    try {
      const res = await api.ingestDischarge({
        patient_name: patient.name,
        patient_phone: patient.phone,
        patient_dob: patient.dob,
        patient_email: patient.email,
        discharge_summary_text: text,
        existing_patient_id: patient.id,
      });
      await fetchPatient();
      router.replace(`/patients/${res.patient_id}`);
      setIntakeBusy(false);
      window.alert(
        `Discharge processed.\nRisk: ${res.risk_level}\nDecision: ${res.decision}\nQuestions: ${res.generated_questions?.length ?? 0}\n\nA voice follow-up is scheduled shortly (demo: ~1-4 min by risk).`,
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Discharge intake failed.";
      setIntakeBusy(false);
      window.alert(message);
    }
  };

  /* ------------------------------ loading / missing ------------------------------ */

  if (!patient) {
    if (!apiAttempted) {
      return (
        <div className="flex flex-1 items-center justify-center px-4 py-20">
          <div className="flex items-center gap-2.5 text-[12.5px] text-[#7a8796]">
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-[#cfd8e1] border-t-[#0f766e]" />
            Opening chart…
          </div>
        </div>
      );
    }
    return (
      <div className="flex flex-1 items-center justify-center px-4 py-16">
        <div className="w-full max-w-md">
          <EmptyState
            title="Chart not found"
            body={
              <>
                No patient record matches MRN{" "}
                <span className="ac-mono font-medium text-slate-700">{id}</span> in the chart service.
              </>
            }
            action={
              <Link href="/" className="ac-btn ac-btn-primary">
                Back to patient panel
              </Link>
            }
          />
        </div>
      </div>
    );
  }

  const age = ageFromIsoDob(patient.dob);
  const ageLabel = age != null ? `${age} y` : patient.dob ? "-" : "Age unknown";
  const unackedAlerts = patient.alerts.filter((a) => !a.acknowledged).length;

  const tabCount: Record<string, number | undefined> = {
    medications: patient.medications.length,
    followup: patient.followup_jobs?.length,
    appointments: patient.appointments.length,
    "ai-calls": voiceInteractions.length,
    alerts: patient.alerts.length,
  };

  return (
    <div className="flex min-h-[calc(100vh-88px)] w-full flex-1 flex-col lg:flex-row lg:items-stretch">
      <div className="order-1 flex min-w-0 flex-1 flex-col">
        <ChartBanner patient={patient} ageLabel={ageLabel} onScheduleFollowup={() => setScheduleFollowupOpen(true)} />

        {/* ----------------------------- Tab strip ----------------------------- */}
        <div className="sticky top-[88px] z-20 border-b border-[#e3e8ee] bg-white/95 backdrop-blur">
          <div className="ac-scroll flex items-stretch overflow-x-auto px-2 sm:px-4">
            {TABS.map((tab) => {
              const active = activeTab === tab.id;
              const count = tabCount[tab.id];
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => {
                    setActiveTab(tab.id);
                    if (tab.id === "ai-calls" || tab.id === "followup") void fetchPatient();
                  }}
                  className={cn(
                    "relative flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2.5 text-[12.5px] transition-colors",
                    active
                      ? "border-[#0f766e] font-semibold text-[#0b5d57]"
                      : "border-transparent font-medium text-[#6b7a8a] hover:text-slate-900",
                  )}
                  aria-current={active ? "page" : undefined}
                >
                  {tab.label}
                  {count !== undefined && count > 0 && (
                    <span
                      className={cn(
                        "min-w-[16px] rounded-full px-1 text-center text-[10px] font-semibold leading-[15px]",
                        tab.id === "alerts" && unackedAlerts > 0
                          ? "bg-[#fdecea] text-[#b42318]"
                          : "bg-[#f0f3f6] text-[#7a8796]",
                      )}
                    >
                      {count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* ------------------------------ Tab body ------------------------------ */}
        <div className="ac-scroll ac-yield min-w-0 flex-1 px-4 py-4 sm:px-6">
          {activeTab === "overview" && <OverviewTab patient={patient} />}
          {activeTab === "medical" && <MedicalHistoryTab patient={patient} />}
          {activeTab === "medications" && <MedicationsTab patient={patient} />}
          {activeTab === "followup" && (
            <FollowupTab patient={patient} onSchedule={() => setScheduleFollowupOpen(true)} />
          )}
          {activeTab === "appointments" && <AppointmentsTab patient={patient} />}
          {activeTab === "ai-calls" && <CallHistoryTab interactions={voiceInteractions} />}
          {activeTab === "alerts" && <AlertsTab alerts={patient.alerts} />}
        </div>
      </div>

      <ScheduleFollowupModal
        open={scheduleFollowupOpen}
        onOpenChange={setScheduleFollowupOpen}
        patientId={patient.id}
        onScheduled={fetchPatient}
      />
      <PatientDetailRightRail patient={patient} intakeBusy={intakeBusy} onDischargeFile={handleDischargeFile} />
    </div>
  );
}
