/** Patient chart formatting shared by the dashboard routes. */

/** Age in years from ISO DOB (YYYY-MM-DD). */
export function ageFromIsoDob(dob: string | null | undefined): number | null {
  if (!dob || dob.length < 10) return null;
  const born = new Date(`${dob.slice(0, 10)}T12:00:00Z`);
  if (Number.isNaN(born.getTime())) return null;
  const today = new Date();
  let age = today.getUTCFullYear() - born.getUTCFullYear();
  const md = today.getUTCMonth() * 100 + today.getUTCDate() - (born.getUTCMonth() * 100 + born.getUTCDate());
  if (md < 0) age -= 1;
  return Math.max(0, age);
}
