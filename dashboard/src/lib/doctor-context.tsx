"use client";

import { createContext, useContext, useState } from "react";
import type { DoctorProfile } from "@/lib/doctors";

export type { DoctorProfile };

interface DoctorContextValue {
  doctor: DoctorProfile | null;
  setDoctor: (doctor: DoctorProfile | null) => void;
  logout: () => void;
}

const DoctorContext = createContext<DoctorContextValue>({
  doctor: null,
  setDoctor: () => {},
  logout: () => {},
});

const STORAGE_KEY = "aftercare_doctor";

function readStoredDoctor(): DoctorProfile | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored ? (JSON.parse(stored) as DoctorProfile) : null;
  } catch {
    return null;
  }
}

/**
 * Remembers which clinician is signed in (demo auth: no password, just a pick).
 * The selection is mirrored to localStorage so refreshes keep the same view.
 */
export function DoctorProvider({ children }: { children: React.ReactNode }) {
  const [doctor, setDoctorState] = useState<DoctorProfile | null>(readStoredDoctor);

  const setDoctor = (next: DoctorProfile | null) => {
    setDoctorState(next);
    if (next) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  };

  const logout = () => setDoctor(null);

  return (
    <DoctorContext.Provider value={{ doctor, setDoctor, logout }}>
      {children}
    </DoctorContext.Provider>
  );
}

export function useDoctor() {
  return useContext(DoctorContext);
}
