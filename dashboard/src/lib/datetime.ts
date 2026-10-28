/**
 * All AfterCare Voice dashboard dates/times are shown in US Eastern (handles EST/EDT via IANA zone).
 * Backend APIs store UTC; we only change presentation here.
 */
export const DISPLAY_TIME_ZONE = "America/New_York";

const easternFormatter: Intl.DateTimeFormatOptions = {
  timeZone: DISPLAY_TIME_ZONE,
  dateStyle: "medium",
  timeStyle: "short",
};

/**
 * Parse API datetime strings. SQLite returns naive UTC; FastAPI JSON often omits `Z`.
 * `new Date("2026-03-29T12:00:00")` is interpreted as *local* time in JS: wrong for our UTC instants.
 */
function parseUtcInstantFromApi(iso: string): Date {
  const s = iso.trim();
  if (/[zZ]$/.test(s)) {
    return new Date(s);
  }
  // Ends with +HH:MM, +HHMM, or -HH:MM offset
  if (/[+-]\d{2}:\d{2}$/.test(s) || /[+-]\d{4}$/.test(s)) {
    return new Date(s);
  }
  const normalized = s.includes("T") ? s : s.replace(" ", "T");
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(normalized)) {
    return new Date(`${normalized}Z`);
  }
  return new Date(s);
}

/**
 * Format an ISO-8601 instant for display in Eastern Time.
 */
export function formatEasternDateTime(iso: string | null | undefined): string {
  if (iso == null || iso === "") return "-";
  const d = parseUtcInstantFromApi(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString("en-US", easternFormatter);
}

/**
 * File `lastModified` is an epoch ms in local browser time; show it as Eastern for consistency with callbacks.
 */
export function formatEasternFromEpochMs(ms: number): string {
  const d = new Date(ms);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString("en-US", easternFormatter);
}

/**
 * Default date (YYYY-MM-DD) and time (HH:mm) inputs for US Eastern, ~10 minutes from now.
 */
/** YYYY-MM-DD for "today" in US Eastern (calendar navigation / grouping). */
export function easternTodayDateKey(): string {
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone: DISPLAY_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const parts = fmt.formatToParts(new Date());
  const get = (t: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === t)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

/** Map an API instant to YYYY-MM-DD in US Eastern (for grouping appointments by calendar day). */
export function apiInstantToEasternDateKey(iso: string | null): string | null {
  if (iso == null || iso === "") return null;
  const d = parseUtcInstantFromApi(iso);
  if (Number.isNaN(d.getTime())) return null;
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone: DISPLAY_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const parts = fmt.formatToParts(d);
  const get = (t: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === t)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

/** Short time in US Eastern (e.g. sidebar list). */
export function formatEasternTimeOnly(iso: string | null | undefined): string {
  if (iso == null || iso === "") return "-";
  const d = parseUtcInstantFromApi(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleTimeString("en-US", {
    timeZone: DISPLAY_TIME_ZONE,
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

export function defaultEasternDateTimeParts(): { date: string; time: string } {
  const plus = new Date(Date.now() + 10 * 60 * 1000);
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone: DISPLAY_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const parts = fmt.formatToParts(plus);
  const get = (t: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === t)?.value ?? "";
  const y = get("year");
  const m = get("month");
  const d = get("day");
  const h = get("hour");
  const min = get("minute");
  return {
    date: `${y}-${m}-${d}`,
    time: `${h}:${min}`,
  };
}
