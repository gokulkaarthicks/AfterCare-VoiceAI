"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import {
  appointmentTone,
  avatarTint,
  followupTone,
  initialsOf,
  riskTone,
  severityTone,
  statusTone,
} from "@/lib/clinical-vocab";

/* ------------------------------------------------------------------ Pill */

export function StatusPill({ tone, label, className }: { tone: ReturnType<typeof statusTone>; label?: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-[21px] items-center gap-1.5 whitespace-nowrap rounded-[4px] border px-1.5 text-[11px] font-semibold leading-none",
        className,
      )}
      style={{ color: tone.fg, background: tone.bg, borderColor: tone.border }}
    >
      <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: tone.dot }} />
      {label ?? tone.label}
    </span>
  );
}

export function PatientPill({ status, className }: { status: string; className?: string }) {
  return <StatusPill tone={statusTone(status)} className={className} />;
}

export function SeverityPill({ severity, className }: { severity: string; className?: string }) {
  return <StatusPill tone={severityTone(severity)} label={severity.toUpperCase()} className={className} />;
}

/* ---------------------------------------------------------------- Avatar */

export function Avatar({ name, id, size = 26 }: { name: string; id?: string; size?: number }) {
  const tint = avatarTint(id ?? name);
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-full font-semibold"
      style={{
        width: size,
        height: size,
        background: tint.bg,
        color: tint.fg,
        fontSize: Math.max(9, Math.round(size * 0.36)),
        boxShadow: "inset 0 0 0 1px rgb(15 23 42 / 0.06)",
      }}
    >
      {initialsOf(name)}
    </span>
  );
}

/* ----------------------------------------------------------------- Panel */

/** The one card container used everywhere (also exported as ChartPanel). */
export function Panel({
  title,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={cn("ac-card overflow-hidden", className)}>
      {title && (
        <header className="ac-panel-head">
          <h2 className="truncate text-[12.5px] font-semibold text-slate-900">{title}</h2>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn("p-4", bodyClassName)}>{children}</div>
    </section>
  );
}

/* ------------------------------------------------------ Labelled value row */

export function FieldRow({ label, children, mono }: { label: string; children: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <dt className="shrink-0 text-[11.5px] text-[#6b7a8a]">{label}</dt>
      <dd className={cn("text-right text-[12.5px] font-medium text-slate-900", mono && "ac-mono")}>{children}</dd>
    </div>
  );
}

export function EmptyState({
  title,
  body,
  action,
  className,
}: {
  title: string;
  body?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-10 text-center", className)}>
      <p className="text-[13px] font-semibold text-slate-800">{title}</p>
      {body && <p className="mt-1 max-w-md text-[12px] leading-relaxed text-[#7a8796]">{body}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

/* --------------------------------------------------------- Section header */

export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <h1 className="text-[15px] font-semibold tracking-[-0.01em] text-slate-900">{children}</h1>
      {right && <div className="flex items-center gap-2">{right}</div>}
    </div>
  );
}

/* ----------------------------------------------------------------- Vitals */

export type Vital = { label: string; value: string; unit?: string; state?: "normal" | "warn" | "critical" };

const VITAL_STATE = {
  normal: { color: "#0f172a", dot: "#12a150" },
  warn: { color: "#8a5106", dot: "#e08600" },
  critical: { color: "#9a1c12", dot: "#d92d20" },
} as const;

export function VitalsStrip({ vitals }: { vitals: Vital[] }) {
  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[5px] bg-[#eef2f5] sm:grid-cols-3 lg:grid-cols-5">
      {vitals.map((v) => {
        const s = VITAL_STATE[v.state ?? "normal"];
        return (
          <div key={v.label} className="bg-white px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-[#8a97a6]">{v.label}</p>
            <p className="ac-num mt-1 flex items-baseline gap-1 text-[15px] font-semibold leading-none" style={{ color: s.color }}>
              {v.value}
              {v.unit && <span className="text-[10px] font-medium text-[#8a97a6]">{v.unit}</span>}
            </p>
            <span className="mt-1.5 flex items-center gap-1 text-[10px] text-[#a3aeb9]">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.dot }} />
              {v.state === "warn" ? "Monitor" : v.state === "critical" ? "Abnormal" : "Normal"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* Re-exported helpers kept for existing call sites. */
export { appointmentTone, followupTone, riskTone };
