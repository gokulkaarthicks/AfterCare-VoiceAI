import { cn } from "@/lib/cn";

/** AfterCare pulse mark: teal rounded-square with a soft ECG trace. */
export function BrandMark({ size = 30, className }: { size?: number; className?: string }) {
  return (
    <span
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-[8px]",
        className,
      )}
      style={{
        width: size,
        height: size,
        background: "linear-gradient(150deg, #14a497 0%, #0f766e 55%, #0b5d57 100%)",
        boxShadow: "inset 0 1px 0 rgb(255 255 255 / 0.18), 0 1px 2px rgb(11 93 87 / 0.35)",
      }}
      aria-hidden
    >
      <svg
        width={Math.round(size * 0.68)}
        height={Math.round(size * 0.68)}
        viewBox="0 0 24 24"
        fill="none"
        stroke="#ffffff"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M2.5 12.5h4.2l2.3-6.4 3.6 12.4 2.5-6h6.4" />
      </svg>
    </span>
  );
}

/** Horizontal lockup: mark + wordmark, sized for app chrome. */
export function BrandLockup({
  size = 26,
  tone = "light",
  showProduct = true,
}: {
  size?: number;
  tone?: "light" | "dark";
  showProduct?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <BrandMark size={size} />
      <span className="flex flex-col leading-none">
        <span
          className={cn(
            "text-[15px] font-semibold tracking-[-0.015em]",
            tone === "light" ? "text-slate-900" : "text-white",
          )}
        >
          AfterCare
        </span>
        {showProduct && (
          <span
            className={cn(
              "mt-[3px] text-[9.5px] font-semibold uppercase tracking-[0.14em]",
              tone === "light" ? "text-slate-400" : "text-white/55",
            )}
          >
            Voice AI
          </span>
        )}
      </span>
    </span>
  );
}
