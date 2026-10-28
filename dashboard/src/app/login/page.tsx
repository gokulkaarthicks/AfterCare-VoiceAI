"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useDoctor } from "@/lib/doctor-context";
import { DEFAULT_DOCTOR, DEMO_DOCTORS, findDoctor } from "@/lib/doctors";
import { Avatar } from "@/components/aftercare/clinical-ui";
import { BrandMark } from "@/components/aftercare/brand";
import { cn } from "@/lib/cn";

export default function LoginPage() {
  const { setDoctor } = useDoctor();
  const router = useRouter();
  const [selected, setSelected] = useState(DEFAULT_DOCTOR.id);

  const signIn = () => {
    setDoctor(findDoctor(selected));
    router.push("/");
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--app-canvas)] px-4 py-10">
      <div className="w-full max-w-[380px]">
        <div className="mb-6 flex items-center gap-2.5">
          <BrandMark size={28} />
          <div>
            <p className="text-[15px] font-semibold leading-none text-slate-900">AfterCare - Voice AI</p>
            <p className="mt-1 text-[10.5px] text-[#8a97a6]">Post-discharge care</p>
          </div>
        </div>

        <h1 className="text-[18px] font-semibold tracking-[-0.015em] text-slate-900">Sign in</h1>
        <p className="mt-1 text-[12.5px] text-[#6b7a8a]">Choose a provider profile.</p>

        <div className="mt-4 overflow-hidden rounded-[7px] border border-[#e3e8ee] bg-white">
          {DEMO_DOCTORS.map((doc, i) => {
            const active = selected === doc.id;
            return (
              <button
                key={doc.id}
                type="button"
                onClick={() => setSelected(doc.id)}
                onDoubleClick={signIn}
                aria-pressed={active}
                className={cn(
                  "flex w-full items-center gap-2.5 px-3 py-2.5 text-left",
                  i > 0 && "border-t border-[#eef2f5]",
                  active ? "bg-[#f1f8f7]" : "hover:bg-[#f8fafb]",
                )}
              >
                <span
                  className={cn(
                    "flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border",
                    active ? "border-[#0f766e]" : "border-[#c3ccd5]",
                  )}
                >
                  {active && <span className="h-1.5 w-1.5 rounded-full bg-[#0f766e]" />}
                </span>
                <Avatar name={doc.name} id={doc.id} size={30} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12.5px] font-semibold text-slate-900">{doc.name}</span>
                  <span className="block truncate text-[11px] text-[#8a97a6]">{doc.specialty}</span>
                </span>
              </button>
            );
          })}
        </div>

        <button type="button" onClick={signIn} className="ac-btn ac-btn-primary mt-4 w-full !h-9">
          Continue
        </button>

        <p className="mt-6 text-center text-[10.5px] text-[#a3aeb9]">Demo environment · synthetic patient data</p>
      </div>
    </div>
  );
}
