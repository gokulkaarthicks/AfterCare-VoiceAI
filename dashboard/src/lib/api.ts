const DB_SERVICE_URL = process.env.NEXT_PUBLIC_DB_SERVICE_URL || "http://localhost:8003";
const TRIAGE_AGENT_URL = process.env.NEXT_PUBLIC_TRIAGE_AGENT_URL || "http://localhost:8001";
const SCHEDULER_URL = process.env.NEXT_PUBLIC_SCHEDULER_URL || "http://localhost:8004";

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export interface PatientSummary {
  id: string;
  name: string;
  phone: string;
  status: string;
  risk_level: string | null;
  created_at: string | null;
  dob?: string | null;
  /** Latest discharge diagnosis: ward table "Reason". */
  reason?: string | null;
  /** Ward/bed from latest appointment notes (see demo seed). */
  ward?: string | null;
  /** Server-computed age from `dob`. */
  age?: number | null;
}

export interface PatientDetail {
  id: string;
  name: string;
  phone: string;
  dob: string | null;
  email: string | null;
  status: string;
  risk_level: string | null;
  created_at: string | null;
  discharge_summary: {
    id: string;
    diagnosis: string;
    procedures: string | null;
    discharge_date: string | null;
    instructions: string | null;
    raw_text: string;
    created_at: string;
  } | null;
  medications: { id: string; name: string; dosage: string; frequency: string }[];
  questionnaire: {
    id: string;
    questions: { id: string; text: string; question_type: string; relevance: string }[];
    diagnosis_context: string;
    generated_at: string;
  } | null;
  interactions: {
    id: string;
    interaction_type: string;
    channel: string;
    /** Backend may store `question` (from event pipeline) or `question_text`. */
    responses: { question_id?: string; question_text?: string; question?: string; answer: string }[] | null;
    created_at: string;
  }[];
  alerts: {
    id: string;
    alert_type: string;
    severity: string;
    message: string;
    acknowledged: boolean;
    created_at: string;
  }[];
  appointments: {
    id: string;
    appointment_type: string;
    scheduled_at: string | null;
    status: string;
    notes: string | null;
    created_at: string;
  }[];
  /** Scheduled follow-up call jobs (from schedule_event pipeline). */
  followup_jobs: {
    id: string;
    job_type: string;
    scheduled_at: string | null;
    status: string;
    executed_at: string | null;
    completed_at: string | null;
    correlation_id: string | null;
    created_at: string;
  }[];
}

export interface AlertItem {
  id: string;
  patient_id: string;
  patient_name: string | null;
  alert_type: string;
  severity: string;
  message: string;
  acknowledged: boolean;
  created_at: string | null;
}

export interface AppointmentItem {
  id: string;
  patient_id: string;
  patient_name: string | null;
  appointment_type: string;
  scheduled_at: string | null;
  status: string;
  notes: string | null;
  doctor_name: string | null;
  created_at: string | null;
}

export interface FollowupJobItem {
  id: string;
  patient_id: string;
  patient_name: string | null;
  job_type: string;
  scheduled_at: string | null;
  status: string;
  executed_at: string | null;
  completed_at: string | null;
  correlation_id: string | null;
  created_at: string | null;
}

export interface TimelineEntry {
  id: string;
  event_type: string;
  patient_id: string;
  patient_name: string | null;
  summary: string;
  created_at: string | null;
  details: Record<string, unknown>;
}

export interface DischargeIntakeRequest {
  patient_name: string;
  patient_phone: string;
  patient_dob: string | null;
  patient_email: string | null;
  discharge_summary_text: string;
  /** When set, intake updates this patient row instead of creating a new id (matches seeded/demo IDs). */
  existing_patient_id?: string | null;
}

export interface DischargeIntakeResponse {
  patient_id: string;
  risk_level: string;
  decision: string;
  generated_questions: unknown[];
  correlation_id: string;
}

export const api = {
  getPatients: () => fetchJson<PatientSummary[]>(`${DB_SERVICE_URL}/patients`),
  getPatient: (id: string) => fetchJson<PatientDetail>(`${DB_SERVICE_URL}/patients/${id}`),
  getAlerts: () => fetchJson<AlertItem[]>(`${DB_SERVICE_URL}/alerts`),
  acknowledgeAlert: (id: string) =>
    fetchJson<{ id: string; acknowledged: boolean }>(`${DB_SERVICE_URL}/alerts/${id}/acknowledge`, {
      method: "PATCH",
    }),
  getAppointments: (doctorId?: string) =>
    fetchJson<AppointmentItem[]>(
      `${DB_SERVICE_URL}/appointments${doctorId ? `?doctor_id=${encodeURIComponent(doctorId)}` : ""}`
    ),
  getFollowupJobs: (status?: string) =>
    fetchJson<FollowupJobItem[]>(
      `${DB_SERVICE_URL}/followup-jobs${status ? `?status=${encodeURIComponent(status)}` : ""}`
    ),
  getTimeline: (patientId: string) =>
    fetchJson<TimelineEntry[]>(`${DB_SERVICE_URL}/patients/${patientId}/timeline`),
  triggerFollowup: (patientId: string) =>
    fetchJson<{ status: string }>(`${SCHEDULER_URL}/trigger/${patientId}`, { method: "POST" }),
  /** Doctor-scheduled voice follow-up; times are US Eastern, resolved server-side. */
  scheduleDoctorFollowup: (
    patientId: string,
    body: { eastern_date: string; eastern_time: string },
  ) =>
    fetchJson<{ correlation_id: string; scheduled_at: string }>(
      `${DB_SERVICE_URL}/patients/${patientId}/schedule-followup`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  /** Triage Agent: same pipeline as scripts/demo_flow.py step 1. Returns new patient_id. */
  ingestDischarge: (body: DischargeIntakeRequest) =>
    fetchJson<DischargeIntakeResponse>(`${TRIAGE_AGENT_URL}/intake`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
