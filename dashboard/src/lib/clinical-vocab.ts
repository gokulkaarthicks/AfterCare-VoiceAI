/**
 * Clinical vocabulary for the UI: patient status, risk level, and appointment
 * status. Callers keep the stable `key` and render `label`: the display text is
 * unchanged from the backend values, only the visual treatment is new.
 */

export type StatusTone = {
  /** Short human label. */
  label: string;
  /** Solid text color. */
  fg: string;
  /** Soft pill background. */
  bg: string;
  /** Pill border. */
  border: string;
  /** Saturated dot / bar color. */
  dot: string;
};

export const STATUS_TONES: Record<string, StatusTone> = {
  Stable: { label: "Stable", fg: "#0b6b3a", bg: "#e8f6ee", border: "#bfe4cf", dot: "#12a150" },
  Recovering: { label: "Recovering", fg: "#0b5da8", bg: "#e9f2fe", border: "#c2daf9", dot: "#2f7fe0" },
  "High Risk": { label: "High Risk", fg: "#9a1c12", bg: "#fdecea", border: "#f5c2bb", dot: "#d92d20" },
  Discharged: { label: "Discharged", fg: "#3f4a58", bg: "#f0f3f6", border: "#d8dee5", dot: "#7a8796" },
  Admitted: { label: "Admitted", fg: "#0b5da8", bg: "#e9f2fe", border: "#c2daf9", dot: "#2f7fe0" },
};

const STATUS_FALLBACK: StatusTone = {
  label: "Unknown",
  fg: "#3f4a58",
  bg: "#f0f3f6",
  border: "#d8dee5",
  dot: "#7a8796",
};

export function statusTone(status: string | null | undefined): StatusTone {
  if (!status) return { ...STATUS_FALLBACK, label: "-" };
  return STATUS_TONES[status] ?? { ...STATUS_FALLBACK, label: status };
}

export const RISK_TONES: Record<string, StatusTone> = {
  high: { label: "High risk", fg: "#9a1c12", bg: "#fdecea", border: "#f5c2bb", dot: "#d92d20" },
  medium: { label: "Moderate risk", fg: "#8a5106", bg: "#fff4e0", border: "#f3d9a7", dot: "#e08600" },
  low: { label: "Low risk", fg: "#0b6b3a", bg: "#e8f6ee", border: "#bfe4cf", dot: "#12a150" },
};

export function riskTone(risk: string | null | undefined): StatusTone | null {
  if (!risk) return null;
  return RISK_TONES[risk.toLowerCase()] ?? null;
}

/** Appointment lifecycle: same labels the app already used. */
export const APPOINTMENT_STATUS: Record<string, StatusTone> = {
  confirmed: { label: "Confirmed", fg: "#0b6b3a", bg: "#e8f6ee", border: "#bfe4cf", dot: "#12a150" },
  scheduled: { label: "Scheduled", fg: "#0b5da8", bg: "#e9f2fe", border: "#c2daf9", dot: "#2f7fe0" },
  completed: { label: "Completed", fg: "#0b6b3a", bg: "#e8f6ee", border: "#bfe4cf", dot: "#12a150" },
  cancelled: { label: "Cancelled", fg: "#3f4a58", bg: "#f0f3f6", border: "#d8dee5", dot: "#9aa6b4" },
  pending: { label: "Pending", fg: "#8a5106", bg: "#fff4e0", border: "#f3d9a7", dot: "#e08600" },
  pending_confirmation: {
    label: "Awaiting confirmation",
    fg: "#475569",
    bg: "#f2f5f8",
    border: "#dde3e9",
    dot: "#94a3b8",
  },
  pending_manual: {
    label: "Needs scheduling",
    fg: "#9a3412",
    bg: "#fff2e8",
    border: "#f6cfb5",
    dot: "#ea580c",
  },
  in_progress: { label: "In progress", fg: "#0b5da8", bg: "#e9f2fe", border: "#c2daf9", dot: "#2f7fe0" },
  failed: { label: "Failed", fg: "#9a1c12", bg: "#fdecea", border: "#f5c2bb", dot: "#d92d20" },
};

export function appointmentTone(status: string | null | undefined): StatusTone {
  if (!status) return STATUS_FALLBACK;
  return (
    APPOINTMENT_STATUS[status] ?? {
      ...STATUS_FALLBACK,
      label: status.replace(/_/g, " "),
    }
  );
}

export const SEVERITY_TONES: Record<string, StatusTone> = {
  critical: { label: "Critical", fg: "#ffffff", bg: "#b42318", border: "#b42318", dot: "#ffffff" },
  high: { label: "High", fg: "#9a1c12", bg: "#fdecea", border: "#f5c2bb", dot: "#d92d20" },
  medium: { label: "Medium", fg: "#8a5106", bg: "#fff4e0", border: "#f3d9a7", dot: "#e08600" },
  low: { label: "Low", fg: "#0b5da8", bg: "#e9f2fe", border: "#c2daf9", dot: "#2f7fe0" },
};

export function severityTone(severity: string | null | undefined): StatusTone {
  if (!severity) return STATUS_FALLBACK;
  return SEVERITY_TONES[severity.toLowerCase()] ?? { ...STATUS_FALLBACK, label: severity.toUpperCase() };
}

export const FOLLOWUP_STATUS: Record<string, StatusTone> = {
  pending: { label: "Scheduled", fg: "#8a5106", bg: "#fff4e0", border: "#f3d9a7", dot: "#e08600" },
  scheduled: { label: "Scheduled", fg: "#0b5da8", bg: "#e9f2fe", border: "#c2daf9", dot: "#2f7fe0" },
  in_progress: { label: "Calling now", fg: "#0b5da8", bg: "#e9f2fe", border: "#c2daf9", dot: "#2f7fe0" },
  running: { label: "Calling now", fg: "#0b5da8", bg: "#e9f2fe", border: "#c2daf9", dot: "#2f7fe0" },
  completed: { label: "Completed", fg: "#0b6b3a", bg: "#e8f6ee", border: "#bfe4cf", dot: "#12a150" },
  failed: { label: "Failed", fg: "#9a1c12", bg: "#fdecea", border: "#f5c2bb", dot: "#d92d20" },
  cancelled: { label: "Cancelled", fg: "#3f4a58", bg: "#f0f3f6", border: "#d8dee5", dot: "#9aa6b4" },
};

export function followupTone(status: string | null | undefined): StatusTone {
  if (!status) return STATUS_FALLBACK;
  return FOLLOWUP_STATUS[status] ?? { ...STATUS_FALLBACK, label: status.replace(/_/g, " ") };
}

/** Deterministic avatar tint for a person/patient: calm, low-saturation. */
const AVATAR_PALETTE = [
  { bg: "#e6f4f2", fg: "#0b5d57" },
  { bg: "#e9f2fe", fg: "#14509a" },
  { bg: "#f4ecfd", fg: "#5b21b6" },
  { bg: "#fdf2e9", fg: "#9a4a0b" },
  { bg: "#e8f6ee", fg: "#0b6b3a" },
  { bg: "#fdeef3", fg: "#9d174d" },
  { bg: "#eef1f8", fg: "#334155" },
];

export function avatarTint(seed: string) {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return AVATAR_PALETTE[h % AVATAR_PALETTE.length];
}

export function initialsOf(name: string): string {
  const parts = name
    .replace(/[^A-Za-z\s'-]/g, "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0) return "??";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
