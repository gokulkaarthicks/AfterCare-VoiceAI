"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ChevronDown, Search } from "lucide-react";
import { cn } from "@/lib/cn";
import { useDoctor } from "@/lib/doctor-context";
import { Avatar } from "./clinical-ui";
import { BrandMark } from "./brand";

const NAV = [
  { id: "patients", label: "Patients", href: "/", active: (p: string) => p === "/" || p.startsWith("/patients") },
  { id: "schedule", label: "Schedule", href: "/appointments", active: (p: string) => p.startsWith("/appointments") },
  { id: "alerts", label: "Alerts", href: "/alerts", active: (p: string) => p.startsWith("/alerts") },
  { id: "activity", label: "Activity", href: "/timeline", active: (p: string) => p.startsWith("/timeline") },
];

function Menu({
  trigger,
  children,
}: {
  trigger: React.ReactNode;
  children: (close: () => void) => React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex h-8 items-center gap-1.5 rounded-[5px] px-2 text-[12.5px] font-medium text-[#3f4a58] hover:bg-black/[0.04]"
      >
        {trigger}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden />
          <div className="ac-enter absolute right-0 top-[calc(100%+6px)] z-50 min-w-[200px] overflow-hidden rounded-[7px] border border-[#e3e8ee] bg-white py-1 shadow-[0_8px_24px_rgb(15_23_42/0.14)]">
            {children(() => setOpen(false))}
          </div>
        </>
      )}
    </div>
  );
}

function MenuItem({ label, onClick, danger }: { label: string; onClick?: () => void; danger?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "block w-full px-3 py-1.5 text-left text-[12.5px] hover:bg-[#f5f9f8]",
        danger ? "text-[#b42318]" : "text-[#1f2937]",
      )}
    >
      {label}
    </button>
  );
}

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { doctor, logout } = useDoctor();

  useEffect(() => {
    if (!doctor && pathname !== "/login") router.replace("/login");
  }, [doctor, pathname, router]);

  if (pathname === "/login") return <>{children}</>;
  if (!doctor) return null;

  return (
    <div className="flex min-h-screen flex-col bg-[var(--app-canvas)] text-slate-900 antialiased">
      <header className="sticky top-0 z-30 border-b border-[#dfe7e5] bg-[var(--app-chrome)]">
        <div className="flex h-[52px] items-center gap-3 px-4 sm:px-5">
          <Link href="/" className="flex items-center gap-2 pr-1" aria-label="AfterCare Voice home">
            <BrandMark size={22} />
            <span className="hidden text-[13.5px] font-semibold tracking-[-0.01em] text-slate-900 sm:inline">
              AfterCare - Voice AI
            </span>
          </Link>

          <nav className="flex min-w-0 items-center gap-0.5 overflow-x-auto" aria-label="Primary">
            {NAV.map((item) => {
              const active = item.active(pathname);
              return (
                <Link
                  key={item.id}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex h-8 shrink-0 items-center rounded-[5px] px-2.5 text-[12.5px] transition-colors",
                    active
                      ? "bg-white font-semibold text-[#0b5d57] shadow-[inset_0_0_0_1px_#cfe0dd]"
                      : "font-medium text-[#4b5768] hover:bg-black/[0.04]",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-1.5">
            <div className="relative hidden md:block">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#8a97a6]" />
              <input
                placeholder="Search patients"
                className="h-[30px] w-[190px] rounded-[5px] border border-[#dbe4e2] bg-white pl-8 pr-2 text-[12.5px] outline-none focus:border-[#0f766e] lg:w-[240px]"
                aria-label="Search patients"
              />
            </div>

            <Menu
              trigger={
                <>
                  <Avatar name={doctor.name} id={doctor.id} size={22} />
                  <span className="hidden truncate lg:inline">{doctor.name}</span>
                  <ChevronDown className="h-3 w-3 text-[#8a97a6]" />
                </>
              }
            >
              {(close) => (
                <>
                  <div className="mb-1 border-b border-[#eef2f5] px-3 pb-2 pt-1">
                    <p className="truncate text-[12.5px] font-semibold text-slate-900">{doctor.name}</p>
                    <p className="truncate text-[11px] text-[#8a97a6]">{doctor.specialty}</p>
                  </div>
                  <MenuItem label="Settings" onClick={() => close()} />
                  <MenuItem
                    label="Sign out"
                    danger
                    onClick={() => {
                      close();
                      logout();
                      router.replace("/login");
                    }}
                  />
                </>
              )}
            </Menu>
          </div>
        </div>
      </header>

      <main className="flex min-h-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
