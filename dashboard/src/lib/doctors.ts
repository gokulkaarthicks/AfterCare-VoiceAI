/**
 * Fictional clinician roster shown on the sign-in screen.
 *
 * These mirror `shared/fixtures/doctors.py` exactly (ids, names, specialties).
 * The dashboard is a demo, so signing in simply picks which doctor is viewing.
 */
export interface DoctorProfile {
  id: string;
  name: string;
  specialty: string;
  initials: string;
}

export const DEMO_DOCTORS: DoctorProfile[] = [
  { id: "doc-001", name: "Dr. Aris Thorne", specialty: "General Surgery", initials: "AT" },
  { id: "doc-002", name: "Dr. Lena Marsh", specialty: "Internal Medicine", initials: "LM" },
  { id: "doc-003", name: "Dr. Priya Raman", specialty: "Neurosurgery", initials: "PR" },
  { id: "doc-004", name: "Dr. Owen Castellano", specialty: "Cardiology", initials: "OC" },
];

export const DEFAULT_DOCTOR = DEMO_DOCTORS[0];

export function findDoctor(id: string): DoctorProfile {
  return DEMO_DOCTORS.find((doctor) => doctor.id === id) ?? DEFAULT_DOCTOR;
}
