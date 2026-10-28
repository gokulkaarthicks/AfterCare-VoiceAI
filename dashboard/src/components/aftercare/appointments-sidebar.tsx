"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, PhoneCall, Plus } from "lucide-react";
import { api, type AppointmentItem, type FollowupJobItem } from "@/lib/api";
import { apiInstantToEasternDateKey, easternTodayDateKey, formatEasternTimeOnly } from "@/lib/datetime";
import { cn } from "@/lib/cn";
import { useDoctor } from "@/lib/doctor-context";
import { appointmentTone, followupTone } from "@/lib/clinical-vocab";

const WEEK_DAYS = ["S", "M", "T", "W", "T", "F", "S"];

const WEEK_DAYS_LONG = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** Returns the days array for a calendar grid, null = empty leading cell. */
function buildCalendarDays(year: number, month: number): (number | null)[] {
  const firstDayOfWeek = new Date(year, month, 1).getDay(); // 0 = Sun
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const days: (number | null)[] = [];
  for (let i = 0; i < firstDayOfWeek; i++) days.push(null);
  for (let d = 1; d <= daysInMonth; d++) days.push(d);
  return days;
}

function titleCase(str: string): string {
  return str.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

type ScheduleItem = {
  id: string;
  kind: "appointment" | "followup";
  patient_name: string | null;
  status: string;
  scheduled_at: string | null;
  title: string;
  doctor_name?: string | null;
};

/**
 * Right rail: mini calendar and the schedule for the selected day.
 * Appointments come from the DB service scoped to the signed-in doctor; automated
 * voice follow-up jobs are scoped to those same patients.
 */
export function AppointmentsSidebar() {
  const { doctor } = useDoctor();

  const todayKey = useMemo(() => easternTodayDateKey(), []);

  const [currentYear, setCurrentYear] = useState(() => {
    const [y] = todayKey.split("-").map(Number);
    return y;
  });
  const [currentMonth, setCurrentMonth] = useState(() => {
    const [, m] = todayKey.split("-").map(Number);
    return m - 1;
  }); // 0-indexed
  const [selectedDate, setSelectedDate] = useState<string>(todayKey);
  const [appointments, setAppointments] = useState<AppointmentItem[]>([]);
  const [followupJobs, setFollowupJobs] = useState<FollowupJobItem[]>([]);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      try {
        const [apptData, followupData] = await Promise.all([
          api.getAppointments(doctor?.id),
          api.getFollowupJobs(),
        ]);
        if (!cancelled) {
          setAppointments(apptData);
          setFollowupJobs(followupData);
        }
      } catch {
        // silent: rail is non-critical
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 30_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [doctor?.id]);

  const doctorPatientIds = useMemo(() => {
    return new Set(appointments.map((a) => a.patient_id).filter(Boolean));
  }, [appointments]);

  const scheduleByDate = useMemo(() => {
    const map: Record<string, ScheduleItem[]> = {};
    for (const appt of appointments) {
      const key = apiInstantToEasternDateKey(appt.scheduled_at);
      if (!key) continue;
      if (!map[key]) map[key] = [];
      map[key].push({
        id: appt.id,
        kind: "appointment",
        patient_name: appt.patient_name,
        status: appt.status,
        scheduled_at: appt.scheduled_at,
        title: titleCase(appt.appointment_type),
        doctor_name: appt.doctor_name,
      });
    }
    for (const job of followupJobs) {
      if (!doctorPatientIds.has(job.patient_id)) continue;
      const key = apiInstantToEasternDateKey(job.scheduled_at);
      if (!key) continue;
      if (!map[key]) map[key] = [];
      map[key].push({
        id: job.id,
        kind: "followup",
        patient_name: job.patient_name,
        status: job.status,
        scheduled_at: job.scheduled_at,
        title: "Follow-up call",
      });
    }
    return map;
  }, [appointments, followupJobs, doctorPatientIds]);

  const daysWithAppts = useMemo(() => {
    const set = new Set<number>();
    for (const key of Object.keys(scheduleByDate)) {
      const [y, m, d] = key.split("-").map(Number);
      if (y === currentYear && m - 1 === currentMonth) set.add(d);
    }
    return set;
  }, [scheduleByDate, currentYear, currentMonth]);

  const calendarDays = useMemo(() => buildCalendarDays(currentYear, currentMonth), [currentYear, currentMonth]);

  const selectedItems = useMemo(() => {
    return (scheduleByDate[selectedDate] ?? []).slice().sort((a, b) => {
      if (!a.scheduled_at) return 1;
      if (!b.scheduled_at) return -1;
      return a.scheduled_at < b.scheduled_at ? -1 : 1;
    });
  }, [scheduleByDate, selectedDate]);

  const prevMonth = () => {
    if (currentMonth === 0) {
      setCurrentYear((y) => y - 1);
      setCurrentMonth(11);
    } else setCurrentMonth((m) => m - 1);
  };

  const nextMonth = () => {
    if (currentMonth === 11) {
      setCurrentYear((y) => y + 1);
      setCurrentMonth(0);
    } else setCurrentMonth((m) => m + 1);
  };

  const isToday = selectedDate === todayKey;
  const selectedDayNumber = Number(selectedDate.split("-")[2]);
  const selectedWeekday = new Date(`${selectedDate}T12:00:00`).getDay();
  const selectedHeading = `${WEEK_DAYS_LONG[selectedWeekday] ?? ""}, ${MONTH_NAMES[currentMonth]} ${selectedDayNumber}`;

  return (
    <aside className="order-2 flex w-full shrink-0 flex-col border-t border-[#e3e8ee] bg-white lg:min-h-[calc(100vh-88px)] lg:w-[296px] lg:border-l lg:border-t-0">
      <div className="ac-scroll flex flex-1 flex-col overflow-y-auto">
        {/* Section flag */}
        <div className="flex items-center justify-between border-b border-[#eef2f5] px-4 py-2.5">
          <h2 className="text-[12.5px] font-semibold text-slate-900">Schedule</h2>
          <span className="text-[10.5px] text-[#8a97a6]">Eastern</span>
        </div>

        {/* Calendar */}
        <div className="border-b border-[#eef2f5] px-3 pb-3 pt-3">
          <div className="mb-2 flex items-center justify-between px-1">
            <span className="text-[12.5px] font-semibold text-slate-900">
              {MONTH_NAMES[currentMonth]} <span className="ac-num text-[#8a97a6]">{currentYear}</span>
            </span>
            <div className="flex items-center overflow-hidden rounded-[5px] border border-[#e3e8ee]">
              <button
                type="button"
                onClick={prevMonth}
                className="flex h-6 w-6 items-center justify-center text-[#6b7a8a] transition-colors hover:bg-[#f5f9f8] hover:text-[#0b5d57]"
                aria-label="Previous month"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </button>
              <span className="h-6 w-px bg-[#e3e8ee]" />
              <button
                type="button"
                onClick={nextMonth}
                className="flex h-6 w-6 items-center justify-center text-[#6b7a8a] transition-colors hover:bg-[#f5f9f8] hover:text-[#0b5d57]"
                aria-label="Next month"
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          <div className="mb-1 grid grid-cols-7">
            {WEEK_DAYS.map((d, i) => (
              <div
                key={`${d}-${i}`}
                className={cn(
                  "py-0.5 text-center text-[10px] font-semibold uppercase tracking-[0.06em]",
                  i === 0 || i === 6 ? "text-[#b3bdc7]" : "text-[#8a97a6]",
                )}
              >
                {d}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-y-0.5">
            {calendarDays.map((day, i) => {
              if (day === null) return <div key={`pad-${i}`} />;

              const dateKey = `${currentYear}-${String(currentMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
              const isSelected = dateKey === selectedDate;
              const isTodayCell = dateKey === todayKey;
              const hasAppt = daysWithAppts.has(day);
              const dow = new Date(currentYear, currentMonth, day).getDay();

              return (
                <button
                  key={dateKey}
                  type="button"
                  onClick={() => setSelectedDate(dateKey)}
                  aria-label={`${day} ${MONTH_NAMES[currentMonth]}`}
                  aria-pressed={isSelected}
                  className={cn(
                    "relative mx-auto flex h-[26px] w-[26px] items-center justify-center rounded-[4px] text-[11.5px] transition-colors",
                    isSelected
                      ? "bg-[#0f766e] font-semibold text-white shadow-[inset_0_0_0_1px_#0b5d57]"
                      : isTodayCell
                        ? "font-semibold text-[#0b5d57] shadow-[inset_0_0_0_1px_#8cc8c1] hover:bg-[#e6f4f2]"
                        : cn(dow === 0 || dow === 6 ? "text-[#9aa6b4]" : "text-[#334155]", "hover:bg-[#f1f5f9]"),
                  )}
                >
                  <span className="ac-num">{day}</span>
                  {hasAppt && (
                    <span
                      className={cn(
                        "absolute bottom-[2px] left-1/2 h-[3px] w-[3px] -translate-x-1/2 rounded-full",
                        isSelected ? "bg-white/90" : "bg-[#0f766e]",
                      )}
                    />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Selected day */}
        <div className="flex items-center justify-between px-4 pb-2 pt-3">
          <p className="text-[12px] font-semibold text-slate-900">
            {isToday ? "Today" : selectedHeading}
            <span className="ml-1.5 font-normal text-[#8a97a6]">· {selectedItems.length}</span>
          </p>
        </div>

        {selectedItems.length === 0 ? (
          <p className="px-4 pb-6 pt-1 text-[12px] text-[#8a97a6]">Nothing scheduled.</p>
        ) : (
          <ol className="flex flex-col px-2 pb-3">
            {selectedItems.map((item) => {
              const tone = item.kind === "followup" ? followupTone(item.status) : appointmentTone(item.status);
              return (
                <li
                  key={`${item.kind}-${item.id}`}
                  className="group relative flex gap-2.5 rounded-[6px] px-2 py-2 transition-colors hover:bg-[#f7fbfa]"
                >
                  <span
                    className="mt-0.5 w-[3px] shrink-0 self-stretch rounded-full"
                    style={{ background: tone.dot }}
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="ac-num text-[12px] font-semibold text-slate-900">
                        {item.scheduled_at ? formatEasternTimeOnly(item.scheduled_at) : "TBD"}
                      </span>
                      <span className="text-[10px] font-medium text-[#8a97a6]">{tone.label}</span>
                    </div>
                    <p className="mt-0.5 truncate text-[12.5px] font-medium text-slate-800">{item.title}</p>
                    <p className="mt-0.5 flex items-center gap-1 truncate text-[11.5px] text-[#6b7a8a]">
                      {item.kind === "followup" && <PhoneCall className="h-3 w-3 shrink-0 text-[#8a97a6]" />}
                      {item.patient_name ?? "Unassigned"}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>

      {/* Rail footer */}
      <div className="border-t border-[#eef2f5] p-2.5">
        <button
          type="button"
          className="ac-btn ac-btn-secondary w-full"
          aria-label="Create new appointment"
        >
          <Plus className="h-3.5 w-3.5" />
          New appointment
        </button>
      </div>
    </aside>
  );
}
